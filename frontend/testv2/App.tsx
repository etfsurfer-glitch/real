// 지도 개편 시험판(testv2) — design/map_ui/지도UI_개편안.html 을 실제 화면으로.
// 운영 API 는 읽기(GET)만 쓴다. 새 API 가 필요한 곳(구 랭킹·사무소 좌표·호가추이 집계·콕집 매물)은
// 자리만 두고 '준비 중' 으로 표시한다. 운영 페이지는 koczip.com 링크로만 연결.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { loadKakao, wonShort, geocodeRegion } from "../src/lib/kakaomap";
import { areaLabel } from "../src/lib/area";
import { ComplexDrawer, JibunDrawer, Skel, Dd, SPECIAL_KINDS, type DrawerTab, type Jibun } from "./Drawer";
import { useSession, authHeaders, LoginBox, MeModal, logout, sessionName } from "./Request";
import { StatsWindow, statsKeyOf, type StatsKey } from "./Stats";
import { SafeWindow, type SafeTab } from "./Safe";
import { AskWindow, askTabOf, type AskTab } from "./Ask";
import { FavWindow } from "./Fav";
import { RealtorWindow } from "./Realtor";
import { FootBar, FootNote, LegalModal, type LegalKind } from "./Foot";
import { useAds, AdRow, AdInfoModal, type Ad } from "./Ads";

const API = "https://api.koczip.com";
const SITE = "https://koczip.com";

// 지도 표식 아이콘(lucide 선 아이콘, 흰 선)
const svg = (d: string) => `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
const ICO = {
  apt: svg('<path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/><path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/><path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"/><path d="M10 6h4"/><path d="M10 10h4"/><path d="M10 14h4"/><path d="M10 18h4"/>'),
  offi: svg('<rect width="16" height="20" x="4" y="2" rx="2"/><path d="M9 22v-4h6v4"/><path d="M8 6h.01"/><path d="M16 6h.01"/><path d="M12 6h.01"/><path d="M12 10h.01"/><path d="M12 14h.01"/><path d="M16 10h.01"/><path d="M16 14h.01"/><path d="M8 10h.01"/><path d="M8 14h.01"/>'),
  school: svg('<path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/>'),
  train: svg('<path d="M8 3.1V7a4 4 0 0 0 8 0V3.1"/><path d="m9 15-1-1"/><path d="m15 15 1-1"/><path d="M9 19c-2.8 0-5-2.2-5-5v-4a8 8 0 0 1 16 0v4c0 2.8-2.2 5-5 5Z"/><path d="m8 19-2 3"/><path d="m16 19 2 3"/>'),
};
// 수도권 노선 색(공식 노선색). 모르는 노선은 파랑.
const LINE_COLORS: Record<string, string> = {
  "1호선": "#0052a4", "2호선": "#00a84d", "3호선": "#ef7c1c", "4호선": "#00a5de", "5호선": "#996cac", "6호선": "#cd7c2f", "7호선": "#747f00", "8호선": "#e6186c", "9호선": "#bdb092",
  "신분당선": "#d4003b", "경의중앙선": "#77c4a3", "수인분당선": "#f5a200", "분당선": "#f5a200", "공항철도": "#0090d2", "경춘선": "#0c8e72", "우이신설선": "#b0ce18", "신림선": "#6789ca", "서해선": "#81a914", "경강선": "#003da5", "김포골드라인": "#a17800", "에버라인": "#6fb245", "의정부경전철": "#fda600", "GTX-A": "#9a6292",
};
const lineColor = (line: string) => { const key = Object.keys(LINE_COLORS).find((k) => line.includes(k)); return key ? LINE_COLORS[key] : "#1268d3"; };

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
  only: boolean; disc: number; sp: string;   // only=급매만, disc=급매 할인 문턱, sp=특수조건(owner|tenant|loan|"")
  // 2026-11-09 추가: 단지정보(동수·세대당 주차·용적률) · 역세권(도보 분) · 매물보기 조건(확인·최근 확인·가격 내림) · 방/욕실 · 층/방향 · 계약조건(융자금) · 시설(태그)
  bld: number; park: number; far: number; walk: number; verify: string; confirm: number; down: boolean;
  rooms: string[]; baths: string[]; floor: string[]; dirs: string[]; loan: string; tags: string[] };
const FLT0: Flt = { types: ["APT", "ABYG", "JGC"], trade: "A1", pmin: 0, pmax: 0, amin: 0, amax: 0, afrom: 0, ato: 0, hmin: 0, hmax: 0, only: false, disc: 0.03, sp: "",
  bld: 0, park: 0, far: 0, walk: 0, verify: "", confirm: 0, down: false, rooms: [], baths: [], floor: [], dirs: [], loan: "", tags: [] };
const ROOM_OPTS = [{ k: "1", l: "방 1개" }, { k: "2", l: "방 2개" }, { k: "3", l: "방 3개" }, { k: "4", l: "방 4개 이상" }];
const BATH_OPTS = [{ k: "1", l: "욕실 1개" }, { k: "2", l: "욕실 2개" }, { k: "3", l: "욕실 3개 이상" }];
const FLOOR_OPTS = [{ k: "low", l: "저층" }, { k: "mid", l: "중층" }, { k: "high", l: "고층" }, { k: "top", l: "탑층" }];
const DIR_OPTS = ["남향", "남동향", "남서향", "동향", "서향", "북향", "북동향", "북서향"].map((d) => ({ k: d, l: d }));
const TAG_OPTS = ["테라스", "마당", "필로티", "복층", "엘리베이터", "주차가능", "세대당1대", "확장형", "올수리"].map((d) => ({ k: d, l: d === "세대당1대" ? "세대당 주차 1대" : d }));
const BLD_OPTS = [{ l: "전체", v: 0 }, { l: "5개 동 이상", v: 5 }, { l: "10개 동 이상", v: 10 }, { l: "20개 동 이상", v: 20 }];
const PARK_OPTS = [{ l: "전체", v: 0 }, { l: "세대당 1대 이상", v: 1 }, { l: "세대당 1.5대 이상", v: 1.5 }, { l: "세대당 2대 이상", v: 2 }];
const FAR_OPTS = [{ l: "전체", v: 0 }, { l: "200% 이하", v: 200 }, { l: "250% 이하", v: 250 }, { l: "300% 이하", v: 300 }];
const WALK_OPTS = [{ l: "전체", v: 0 }, { l: "도보 5분 이내", v: 5 }, { l: "도보 10분 이내", v: 10 }, { l: "도보 15분 이내", v: 15 }];
const CONFIRM_OPTS = [{ l: "전체", v: 0 }, { l: "오늘 확인", v: 1 }, { l: "최근 7일 확인", v: 7 }, { l: "최근 30일 확인", v: 30 }];
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
  area_min: String(f.amin), area_max: String(f.amax), approve_from: String(f.afrom), approve_to: String(f.ato), hh_min: String(f.hmin), hh_max: String(f.hmax),
  bld_min: String(f.bld), park_min: String(f.park), far_max: String(f.far), walk_max: String(f.walk), verify: f.verify, confirm_days: String(f.confirm), price_down: f.down ? "1" : "0",
  rooms: f.rooms.join(","), baths: f.baths.join(","), floor: f.floor.join(","), dirs: f.dirs.join(","), loan: f.loan, tags: f.tags.join(",") });
// 기간 — 실거래 신고는 계약 후 30일 안에 해야 하고(실측 30일 내 91%·14일 70%), 동 단위 표본은 분기(90일)쯤
// 모여야 유의미하다. 기본 3개월, 더 넓게는 6·12개월. 호가는 스냅샷 보관 때문에 60일 고정.
const PRICE_WINDOWS: { d: number; l: string }[] = [{ d: 90, l: "3개월" }, { d: 180, l: "6개월" }, { d: 365, l: "12개월" }];
const REPORT_LAG = 30;
type Rk = { realtor_id: string; realtor_name: string; listings: number; total_listings?: number; staff_count?: number; tenure_years?: number; established_year?: number | string;
  phone?: string; lat?: number | null; lng?: number | null; address?: string | null; representative?: string | null };
// 지도 핀용 랭킹 행(순위 포함)
type RkPin = Rk & { rank: number; lat: number; lng: number };

// 레이어 이름 = 절충안 상단 묶음 이름. 휴대폰은 짧게.
const LAYERS: { key: Layer; label: string; short: string }[] = [
  { key: "deals", label: "매물찾기", short: "매물" },
  { key: "price", label: "시세분석", short: "시세" },
  { key: "realtor", label: "중개사", short: "중개사" },
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

// 공유 링크: ?layer=&lat=&lng=&lv=&cx=&stats=묶음.항목&safe=탭&ask=탭
function readUrl() {
  const p = new URLSearchParams(location.search);
  const layer = (["deals", "price", "realtor"].includes(p.get("layer") || "") ? p.get("layer") : "deals") as Layer;
  const pm = (["tx", "hoga", "vol", "gap", "rh"].includes(p.get("m") || "") ? p.get("m") : "tx") as PriceMetric;
  const lat = parseFloat(p.get("lat") || ""), lng = parseFloat(p.get("lng") || ""), lv = parseInt(p.get("lv") || "");
  const safe = (["alert", "ledger", "jeonse", "calc"].includes(p.get("safe") || "") ? p.get("safe") : null) as SafeTab | null;
  return { layer, pm, lat: isNaN(lat) ? 37.5045 : lat, lng: isNaN(lng) ? 127.1095 : lng, lv: isNaN(lv) ? 5 : lv, cx: p.get("cx"), stats: statsKeyOf(p.get("stats")), safe, ask: p.get("proposals") ? "mine" as AskTab : askTabOf(p.get("ask")), proposals: p.get("proposals") || "", fav: p.get("fav") === "1", rt: p.get("rt") || null };
}

export default function App() {
  const init = useMemo(readUrl, []);
  const phone = useIsPhone();
  const [layer, setLayer] = useState<Layer>(init.layer);
  // 단지를 누르면 서랍은 지금 보고 있는 레이어의 탭으로 연다
  // 핀 팝업의 실거래·단지·이야기 버튼은 서랍을 그 탭으로 연다(한 번만, 다음 단지부터는 레이어 기본 탭)
  const [tabOv, setTabOv] = useState<DrawerTab | null>(null);
  const drawerTab: DrawerTab = tabOv ?? (layer === "price" ? "tx" : layer === "realtor" ? "realtor" : "deals");
  const [view, setView] = useState<View | null>(null);
  const [region, setRegion] = useState<Region | null>(null);
  const ads = useAds(region?.sgg, region?.dong);   // 지도 광고 5자리(없으면 빈 배열)
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
  // 중개사랭킹 지도 핀: 패널이 정렬한 상위 사무소(순위 포함) + 고른 핀(같은 자리 묶음 키)
  const [rkRows, setRkRows] = useState<(Rk & { rank: number })[]>([]);
  const [rkSel, setRkSel] = useState<string | null>(null);
  const geoRef = useRef(new Map<string, { lat: number; lng: number } | null>());   // 주소 → 좌표(좌표 없는 사무소는 카카오 주소 검색)
  const [geoTick, setGeoTick] = useState(0);
  const [mapErr, setMapErr] = useState("");
  const [hint, setHint] = useState("");
  const [sheet, setSheet] = useState<"peek" | "half" | "full">("half");
  const [more, setMore] = useState(false);
  // 지도 위 창: 통계(옛 실거래·매물호가·거래량·투자 통계를 다시 만든 것) · 안심(등기·전세안심) · 매물의뢰 갈래
  const [stats, setStats] = useState<StatsKey | null>(init.stats);
  const [safe, setSafe] = useState<SafeTab | null>(init.safe);
  const [ask, setAsk] = useState<AskTab | null>(init.ask);
  // 관심단지 대시보드(?fav=1) · 중개사무소 상세(?rt=아이디) — 운영 페이지 대신 지도 안 창
  const [fav, setFav] = useState<boolean>(init.fav);
  const [meOpen, setMeOpen] = useState(false);   // 내 정보(닉네임·휴대폰 인증·로그아웃) 작은 창
  const [legal, setLegal] = useState<LegalKind | null>(null);   // 이용약관·개인정보처리방침 모달
  const [adInfo, setAdInfo] = useState(false);   // 광고 안내(상품·가격·문의)
  const [rt, setRt] = useState<string | null>(init.rt);
  const closeWins = () => { setStats(null); setSafe(null); setAsk(null); setFav(false); setRt(null); setReqOpen(false); };
  const openAsk = (t: AskTab) => { closeWins(); setAsk(t); };
  const openFav = () => { closeWins(); setFav(true); };
  const openRt = (id: string) => { if (!id) return; closeWins(); setRt(id); };
  const [reqOpen, setReqOpen] = useState(false);
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
  const goComplex = useCallback((no: string, name: string, tab?: DrawerTab) => {
    getJson(`/complexes/coords?ids=${no}`).then((j) => {
      const h = j.items?.[0]; if (!h) return;
      const m = mapRef.current;
      if (m) { m.setLevel(4); m.setCenter(new window.kakao.maps.LatLng(h.lat, h.lng)); }
      pickComplex({ complex_no: no, name, lat: h.lat, lng: h.lng }, false, tab);
    }).catch(() => {});
  }, []);   // eslint-disable-line react-hooks/exhaustive-deps
  const goTo = useCallback((lat: number, lng: number, lv = 4) => {
    const m = mapRef.current; if (!m) return;
    m.setLevel(lv); m.setCenter(new window.kakao.maps.LatLng(lat, lng));
    // 휴대폰은 아래 시트가 지도 절반을 덮으니 목표 지점을 위쪽 절반 가운데로
    if (phone) m.panBy(0, Math.round(window.innerHeight * 0.24));
  }, [phone]);

  // 주소창 = 공유 링크
  useEffect(() => {
    if (!view) return;
    const p = new URLSearchParams({ layer, lat: view.lat.toFixed(5), lng: view.lng.toFixed(5), lv: String(view.level) });
    if (layer === "price" && pm !== "tx") p.set("m", pm);
    if (sel) p.set("cx", sel.complex_no);
    if (stats) p.set("stats", `${stats.g}.${stats.i}`);
    if (safe) p.set("safe", safe);
    if (ask) p.set("ask", ask);
    if (ask === "mine" && init.proposals) p.set("proposals", init.proposals);
    if (fav) p.set("fav", "1");
    if (rt) p.set("rt", rt);
    history.replaceState(null, "", "?" + p.toString());
  }, [layer, view, sel, pm, stats, safe, ask, fav, rt]);

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

  const pickComplex = useCallback((c: Cx, pan = true, tab?: DrawerTab) => {
    setTabOv(tab ?? null);
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
    // onAct: 핀 안의 data-t 버튼(팝업의 실거래·단지·이야기) — 그 값으로 따로 처리하고 핀 클릭과 섞이지 않게 한다
    const put = (lat: number, lng: number, html: string, onClick?: () => void, z = 1, yAnchor = 1, onAct?: (t: string) => void) => {
      if (!map) return;
      const el = document.createElement("div");
      el.innerHTML = html;
      if (onClick) el.addEventListener("click", (e) => {
        e.stopPropagation();
        const b = (e.target as HTMLElement).closest("[data-t]");
        if (b && onAct) onAct(b.getAttribute("data-t")!); else onClick();
      });
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
      // 축소하면 단지 핀 대신 동(6~7단계)·구(8단계~) 묶음: 이름 + 급매 매물 건수 + 매물 있는 단지 수. 누르면 그 자리로 확대.
      const drawAgg = (lv: "dong" | "gu") => {
        setInView([]); setHint("");
        getJson(`/map/deals-agg?${b2}&level=${lv}&trade=${flt.trade}`).then((aj) => {
          if (off) return;
          clear();
          for (const a of aj.items || []) {
            put(a.lat, a.lng, `<div class="t2-dagg${a.n_deals ? " has" : ""}"><b>${esc(a.name)}</b><span>급매 <i>${a.n_deals.toLocaleString()}</i></span><span>단지 <i>${a.n_cx.toLocaleString()}</i></span></div>`,
              () => map.setLevel(Math.max(3, map.getLevel() - (lv === "gu" ? 3 : 2)), { anchor: new k.maps.LatLng(a.lat, a.lng) }), a.n_deals ? 6 : 5, 0.5);
          }
        }).catch(() => {});
      };
      if (view.level >= 6) { drawAgg(view.level >= 8 ? "gu" : "dong"); return; }
      Promise.all([getJson(`/map/listings?${b2}&${fltQs(flt)}`), qd, sp]).then(([ml, jd, sj]) => {
        if (off) return;
        clear();
        if (ml.too_wide) { drawAgg("gu"); return; }
        // 단지별 가장 큰 할인 매물 1건(평형·호가·실거래 평균 대비) — 핀 머리띠와 팝업 둘째 줄에 쓴다
        type Dq = { discount: number; area_name: string; asking_min: number; avg_real: number; n_real: number };
        const disc = new Map<string, number>();
        const dq = new Map<string, Dq>();
        for (const d of jd.items || []) {
          disc.set(d.complex_no, Math.min(disc.get(d.complex_no) ?? 0, d.discount));
          if (!dq.has(d.complex_no) || d.discount < dq.get(d.complex_no)!.discount) dq.set(d.complex_no, d);
        }
        const spn = new Map<string, number>();
        for (const d of sj?.items || []) spn.set(d.complex_no, (spn.get(d.complex_no) || 0) + 1);
        let items: (Cx & { n: number; u: number; minp: number | null; maxp: number | null; minr: number | null; area: number | null; areaName: string | null; repp: number | null;
          real: number | null; realYmd: string | null; disc?: number; dq?: Dq; sp?: number })[] = (ml.items || []).map((m: any) => ({
          complex_no: m.complex_no, name: m.name, lat: m.lat, lng: m.lng, households: m.households, listings: m.n,
          n: m.n, u: Math.round(m.units || 0), minp: m.min_price, maxp: m.max_price, minr: m.min_rent, area: m.min_area, areaName: m.min_area_name, repp: m.rep_price ?? null,
          real: m.real_price, realYmd: m.real_ymd, disc: disc.get(m.complex_no), dq: dq.get(m.complex_no), sp: spn.get(m.complex_no),
        }));
        if (flt.only) items = items.filter((c) => c.disc);   // 급매만: 급매가 있는 단지만 남긴다
        if (flt.sp) items = items.filter((c) => c.sp);       // 특수조건: 해당 매물이 있는 단지만
        const kokCx: Cx[] = [];
        setInView(items);
        const spl = SPECIAL_KINDS.find((x) => x.k === flt.sp)?.l;
        setHint(items.length ? "" : flt.sp ? `이 범위엔 ${spl} 매물이 있는 단지가 없어요` : flt.only ? "이 범위엔 조건에 맞는 급매 단지가 없어요" : "이 조건에 맞는 매물이 이 범위엔 없어요");
        // 핀 = 머리띠(최저가 매물의 평형 · 급매/특수조건) + 몸통(매·전·월 최저 호가, 같은 평형 최근 실거래 '실'). 이름은 마우스를 올리면 팝업으로.
        // 팝업: 단지 이름 · 호가 범위 · 급매(가장 큰 할인 1건, 없으면 '급매 없음') · 실거래/단지/이야기 바로가기. 폰은 hover 가 없어 핀 탭 → 서랍.
        const tl = flt.trade === "B1" ? "전" : flt.trade === "B2" ? "월" : "매";
        const tlf = flt.trade === "B1" ? "전세" : flt.trade === "B2" ? "월세" : "매매";
        for (const c of items) {
          const on = c.complex_no === selNo;
          // 몸통 가격 = 대표 평형(세대수 최다)의 최저 호가. 팝업의 범위는 단지 전체 최저~최고.
          const pp = c.repp ?? c.minp;
          const price = pp ? wonShort(pp) + (flt.trade === "B2" && c.minr ? `/${Math.round(c.minr / 1e4)}` : "") : "-";
          const hd = [c.area ? areaLabel(c.area) : (c.areaName ? `${c.areaName}타입` : "매물"), c.disc ? `급매 ${pct(c.disc, 0)}` : "", c.sp ? `${spl} ${c.sp}` : ""].filter(Boolean).join(" · ");
          const range = c.minp ? (c.maxp && c.maxp !== c.minp ? `${wonShort(c.minp)} ~ ${wonShort(c.maxp)}` : wonShort(c.minp)) : "-";
          const deal = c.dq ? `<b>급매</b> ${esc(c.dq.area_name)}타입 ${wonShort(c.dq.asking_min)} <i>실거래 평균 대비 ${pct(c.dq.discount, 0)}</i>` : `<b>급매</b> 없음`;
          put(c.lat, c.lng, `<div class="t2-pw"><div class="t2-pin2${c.disc ? " deal" : ""}${c.sp ? " sp" : ""}${on ? " on" : ""}"><span class="hd">${esc(hd)}</span><b>${tl} ${price}</b>${c.real ? `<em>실 ${wonShort(c.real)}</em>` : ""}</div>
            <div class="t2-pop"><div class="t2-pop-in"><div class="h">${esc(c.name)}</div><div class="p"><span>${tlf}</span>${range}</div><div class="d${c.dq ? " on" : ""}">${deal}</div>
            <div class="a"><button type="button" data-t="tx">실거래</button><button type="button" data-t="info">단지</button><button type="button" data-t="review">이야기</button></div></div></div></div>`,
            () => pickComplex(c, false), on ? 50 : c.disc || c.sp ? 6 : 5, 1, (t) => pickComplex(c, false, t as DrawerTab));
        }
        // 광고 핀(금색 머리띠 '광고'): 분양·입주 현장. 누르면 연결 주소(또는 단지)로
        for (const a of ads.pin) {
          if (!a.lat || !a.lng) continue;
          put(a.lat, a.lng, `<div class="t2-pw"><div class="t2-pin2 ad"><span class="hd">광고${a.sub ? ` · ${esc(a.sub)}` : ""}</span><b>${esc(a.title)}</b>${a.advertiser ? `<em>${esc(a.advertiser)}</em>` : ""}</div></div>`,
            () => { fetch(`${API}/map/ads/${a.id}/click`, { method: "POST" }).catch(() => {}); if (a.complex_no) goComplex(a.complex_no, a.title); else if (a.url) window.open(a.url, "_blank", "noreferrer"); }, 7);
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
  }, [layer, view, selNo, selJ?.ref, rkDong, region?.dong, region?.sgg, pickComplex, pm, pw, pa, flt, ads.pin]);   // eslint-disable-line react-hooks/exhaustive-deps

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
    const put = (lat: number, lng: number, html: string, z = 3) => {
      const el = document.createElement("div"); el.innerHTML = html;
      add(new k.maps.CustomOverlay({ position: new k.maps.LatLng(lat, lng), content: el, xAnchor: 0.5, yAnchor: 0.5, zIndex: z }));
    };
    // 지도 위 표식: 동그란 아이콘 + 글자(흰 테두리). 떠 있는 카드가 아니라 지도 자체의 명소 표시처럼.
    // 단지를 고르면 단지에서 점선이 뻗어 나가고, 선이 닿는 순서로 표식이 통통 튀어 나온다(--d = 지연).
    const DRAW = 450, GAP = 160;
    let seq = 0;
    const poi = (cls: string, color: string, icon: string, name: string, sub: string, delay: number) =>
      `<div class="t2-poi ${cls}" style="--pc:${color};--d:${delay}ms"><i>${icon}</i><b>${esc(name)}</b>${sub ? `<span>${esc(sub)}</span>` : ""}</div>`;
    // 단지 → 역·학교: 얕은 점선을 단지에서부터 그려 나가고(DRAW ms), 다 닿으면 가운데 거리 글자
    const link = (lat: number, lng: number, color: string, m: number, delay: number) => {
      if (!origin) return;
      const o = origin;
      // 그릴 땐 굵고 진하게(눈에 띄게), 다 닿으면 점이 사라지고 선은 얕게 가라앉는다
      const pl = new k.maps.Polyline({ path: [new k.maps.LatLng(o.lat, o.lng), new k.maps.LatLng(o.lat, o.lng)],
        strokeWeight: 3, strokeColor: color, strokeOpacity: 0.95, strokeStyle: "dot", zIndex: 1 });
      add(pl);
      const dotEl = document.createElement("div"); dotEl.innerHTML = `<div class="t2-dot" style="--pc:${color}"></div>`;
      const dot = new k.maps.CustomOverlay({ position: new k.maps.LatLng(o.lat, o.lng), content: dotEl, xAnchor: 0.5, yAnchor: 0.5, zIndex: 5 });
      let t0 = 0, t1 = 0;
      const settle = (now: number) => {
        if (off) return;
        if (!t1) t1 = now;
        const p = Math.min(1, (now - t1) / 700);
        pl.setOptions({ strokeWeight: 3 - 1.5 * p, strokeOpacity: 0.95 - 0.4 * p });
        if (p < 1) requestAnimationFrame(settle);
      };
      const step = (now: number) => {
        if (off) { dot.setMap(null); return; }
        if (!t0) t0 = now;
        const p = Math.min(1, (now - t0) / DRAW), e = 1 - (1 - p) * (1 - p);
        const end = new k.maps.LatLng(o.lat + (lat - o.lat) * e, o.lng + (lng - o.lng) * e);
        pl.setPath([new k.maps.LatLng(o.lat, o.lng), end]);
        dot.setPosition(end);
        if (p < 1) requestAnimationFrame(step);
        else {
          dot.setMap(null);
          put((o.lat + lat) / 2, (o.lng + lng) / 2, `<div class="t2-dist" style="--pc:${color}">${m >= 1000 ? (m / 1000).toFixed(1) + "km" : m + "m"}</div>`, 2);
          requestAnimationFrame(settle);
        }
      };
      setTimeout(() => { if (off) return; add(dot); requestAnimationFrame(step); }, delay);
    };
    // 표식 하나 = 선 + 아이콘(선이 닿을 때쯤 등장)
    const mark = (lat: number, lng: number, cls: string, color: string, icon: string, name: string, sub: string, m: number) => {
      const d = seq++ * GAP;
      put(lat, lng, poi(cls, color, icon, name, sub, d + DRAW - 120));
      link(lat, lng, color, m, d);
    };
    let origin: { lat: number; lng: number } | null = null;
    const pend: (() => void)[] = [];
    const ready = (fn: () => void) => (origin ? fn() : pend.push(fn));
    // 단지 좌표(요약) — 단지 자체는 핀이 있으니 따로 표식을 두지 않는다
    getJson(`/complex/${selNo}/summary`).then((s) => {
      if (off || !s?.latitude) return;
      origin = { lat: s.latitude, lng: s.longitude };
      pend.splice(0).forEach((f) => f());
    }).catch(() => {});
    getJson(`/complex/${selNo}/subway-nearby?radius_km=1.5&limit=3`).then((j) => {
      if (off) return;
      for (const s of j.items || []) {
        const line = String(s.lines || "").split("·")[0].trim();
        ready(() => mark(s.lat, s.lng, "st", lineColor(line), ICO.train, s.station, `${line.replace(/수도권\s+도시철도\s*/, "")} · 도보 ${s.walk_min}분`, s.distance_m));
      }
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
      for (const sc of j.assigned || []) {
        ready(() => mark(sc.lat, sc.lng, "sc", "#1f9d63", ICO.school, String(sc.name).replace("등학교", ""), `${j.src === "near" ? "인근" : "배정"} · 도보 ${sc.walk_min}분`, sc.distance_m));
      }
    }).catch(() => {});
    return () => { off = true; };
  }, [selNo]);

  useEffect(() => { if (layer !== "deals") setHint(""); }, [layer]);

  // ── 중개사랭킹: 사무소 핀 + 지도 안 팝업 ─────────────────────────
  // 좌표 없는 사무소(네이버 프로필 좌표 없음)는 등록 주소로 카카오 주소 검색을 돌려 채운다(한 번 받은 건 기억).
  useEffect(() => {
    if (layer !== "realtor") return;
    let off = false;
    const todo = rkRows.filter((r) => !(r.lat && r.lng) && r.address && !geoRef.current.has(r.address)).slice(0, 60);
    if (!todo.length) return;
    (async () => {
      let n = 0;
      for (const r of todo) {
        if (off) return;
        geoRef.current.set(r.address!, null);
        const hit = await geocodeRegion(r.address!.replace(/\(.*?\)/g, " ").replace(/\s+\S*호\b.*$/, "").trim()).catch(() => null);
        geoRef.current.set(r.address!, hit);
        if (++n % 5 === 0 || n === todo.length) setGeoTick((t) => t + 1);
      }
    })();
    return () => { off = true; };
  }, [layer, rkRows]);
  const rkPins = useMemo<RkPin[]>(() => {
    if (layer !== "realtor") return [];
    const out: RkPin[] = [];
    for (const r of rkRows) {
      const g = r.lat && r.lng ? { lat: r.lat, lng: r.lng } : r.address ? geoRef.current.get(r.address) : null;
      if (g) out.push({ ...r, lat: g.lat, lng: g.lng });
    }
    return out;
  }, [layer, rkRows, geoTick]);   // eslint-disable-line react-hooks/exhaustive-deps
  const rkKey = (p: { lat: number; lng: number }) => `${p.lat.toFixed(5)},${p.lng.toFixed(5)}`;
  const rkOvs = useRef<any[]>([]);
  useEffect(() => {
    const map = mapRef.current, k = window.kakao;
    rkOvs.current.forEach((o) => o.setMap(null)); rkOvs.current = [];
    if (layer !== "realtor" || !map || !k || !rkPins.length) return;
    const add = (o: any) => { o.setMap(map); rkOvs.current.push(o); };
    // 같은 자리(같은 건물·주소)의 사무소는 한 핀으로 묶는다
    const groups = new Map<string, RkPin[]>();
    for (const p of rkPins) { const key = rkKey(p); (groups.get(key) || groups.set(key, []).get(key)!).push(p); }
    const dongName = rkDong?.name || region?.dongName || "동";
    for (const [key, g] of groups) {
      g.sort((a, b) => a.rank - b.rank);
      const top = g[0], on = rkSel === key;
      const el = document.createElement("div");
      el.innerHTML = `<div class="t2-rpin${top.rank === 1 ? " gold" : ""}${g.length > 1 ? " multi" : ""}${on ? " on" : ""}"><i>${top.rank}${g.length > 1 ? `<small>+${g.length - 1}</small>` : ""}</i><b>${esc(g.length > 1 ? `${shortName(top.realtor_name)} 외 ${g.length - 1}` : shortName(top.realtor_name))}</b></div>`;
      el.addEventListener("click", (e) => { e.stopPropagation(); setRkSel((s) => (s === key ? null : key)); });
      add(new k.maps.CustomOverlay({ position: new k.maps.LatLng(top.lat, top.lng), content: el, xAnchor: 0.5, yAnchor: 0.5, clickable: true, zIndex: on ? 40 : 10 + Math.max(0, 50 - top.rank) }));
      if (!on) continue;
      // 팝업: 묶인 사무소 전부, 순위·매물·직원·업력·대표·주소·전화·상세
      const pop = document.createElement("div");
      pop.innerHTML = `<div class="t2-rpop">
        <div class="t2-rpop-h"><b>${esc(dongName)} 중개사</b><span>${g.length}곳 · 같은 자리</span><button class="t2-x" aria-label="닫기">×</button></div>
        <div class="t2-rpop-b">${g.map((r) => `
          <div class="t2-rpop-r">
            <div class="t2-rpop-t"><span class="rk${r.rank === 1 ? " gold" : ""}">${r.rank}위</span><b>${esc(r.realtor_name)}</b></div>
            <div class="t2-rpop-k"><span><em>매물</em>${r.listings.toLocaleString()}건${r.total_listings && r.total_listings > r.listings ? ` <small>전체 ${r.total_listings.toLocaleString()}</small>` : ""}</span><span><em>직원</em>${r.staff_count ?? "-"}명</span><span><em>업력</em>${r.tenure_years ? `${r.tenure_years}년` : "-"}${r.established_year ? ` <small>${r.established_year} 개업</small>` : ""}</span></div>
            <div class="t2-rpop-a">${r.representative ? `대표 ${esc(r.representative)} · ` : ""}${esc(String(r.address || "").replace(/\s*\(.*?\)\s*$/, ""))}</div>
            <div class="t2-rpop-f">${r.phone ? `<a class="t2-telbtn" href="tel:${r.phone.replace(/[^0-9+]/g, "")}">전화 ${esc(r.phone)}</a>` : ""}<button class="t2-lnk" data-rt="${esc(r.realtor_id)}">사무소 상세</button></div>
          </div>`).join("")}</div></div>`;
      pop.querySelector(".t2-x")?.addEventListener("click", (e) => { e.stopPropagation(); setRkSel(null); });
      pop.addEventListener("click", (e) => {
        e.stopPropagation();
        const b = (e.target as HTMLElement).closest("[data-rt]");
        if (b) openRt(b.getAttribute("data-rt") || "");
      });
      add(new k.maps.CustomOverlay({ position: new k.maps.LatLng(top.lat, top.lng), content: pop, xAnchor: 0.5, yAnchor: 1, clickable: true, zIndex: 60 }));
    }
  }, [layer, rkPins, rkSel, rkDong?.name, region?.dongName]);
  // 레이어가 바뀌거나 보던 동이 '다른' 동으로 바뀌면 팝업을 닫는다(줄 클릭으로 동을 처음 고정할 땐 유지)
  useEffect(() => { setRkSel(null); }, [layer]);
  const prevDong = useRef<string | null>(null);
  useEffect(() => {
    const c = rkDong?.code || null;
    if (prevDong.current && c !== prevDong.current) setRkSel(null);
    prevDong.current = c;
  }, [rkDong?.code]);
  // 패널 줄을 누르면 그 사무소로 지도를 옮기고 팝업을 연다. 지도가 옆 동으로 넘어가도 보던 동 랭킹이 바뀌지 않게 동을 고정.
  const pickRealtor = useCallback((r: Rk) => {
    const g = r.lat && r.lng ? { lat: r.lat, lng: r.lng } : r.address ? geoRef.current.get(r.address) : null;
    if (!g) { setHint("이 사무소는 지도에 찍을 좌표가 아직 없어요"); setTimeout(() => setHint(""), 2500); return; }
    if (!rkDong && region?.dong) setRkDong({ code: region.dong, name: region.dongName });
    const m = mapRef.current;
    if (m) { if (m.getLevel() > 4) m.setLevel(4); m.panTo(new window.kakao.maps.LatLng(g.lat, g.lng)); if (phone) setTimeout(() => m.panBy(0, Math.round(window.innerHeight * 0.24)), 350); }
    setRkSel(rkKey(g));
  }, [phone, rkDong, region]);
  // 패널에서 동을 고르면 그 동 랭킹으로 고정하고 지도를 그 동으로 옮긴다(동 중심은 카카오 주소 검색)
  const pickDong = useCallback((d: { code: string; name: string }, path: string) => {
    setRkDong(d);
    geocodeRegion(path).then((g) => {
      const m = mapRef.current; if (!g || !m) return;
      m.setLevel(5); m.setCenter(new window.kakao.maps.LatLng(g.lat, g.lng));
      if (phone) m.panBy(0, Math.round(window.innerHeight * 0.24));
    }).catch(() => {});
  }, [phone]);

  useEffect(() => { setRkDong(null); }, [region?.sgg]);

  // ── 화면 ─────────────────────────────────────────
  const panel = (
    <>
      {layer === "deals" && <DealsPanel region={region} inView={inView} onPick={pickComplex} zoomedOut={!!hint && inView.length === 0} onRequest={() => openAsk("req")} ad={ads.deals_top[0]} />}
      {layer === "price" && isJibun(pa) && <JibunPanel asset={pa} pins={jpins} region={region} win={pw} onWin={setPw} loading={aggLoading} zoomedOut={(view?.level ?? 5) > (pa === "villa" ? 4 : 5)}
        onPick={(p) => { setSel(null); setSelJ({ asset: pa as Jibun["asset"], ref: p.ref, name: p.name, sigungu: region?.sgg || "", lat: p.lat, lng: p.lng }); goTo(p.lat, p.lng, 3); }} />}
      {layer === "price" && !isJibun(pa) && pm === "rh" && <RecordHighPanel rows={rhs} region={region} win={pw} onWin={setPw} loading={aggLoading} onMetric={setPm} onPick={pickComplex} onStats={() => { closeWins(); setStats({ g: "price", i: "rh" }); }} />}
      {layer === "price" && !isJibun(pa) && pm !== "rh" && <PricePanel region={region} agg={agg} level={view?.level ?? 5} metric={pm} onMetric={setPm}
        win={pw} onWin={setPw} loading={aggLoading} meta={aggMeta} onPick={pickComplex}
        onStats={() => { closeWins(); setStats(pm === "hoga" ? { g: "hoga", i: "sum" } : pm === "vol" ? { g: "flow", i: "vol" } : pm === "gap" ? { g: "invest", i: "gap" } : { g: "price", i: "top" }); }} />}
      {layer === "realtor" && <RealtorPanel region={region} dong={rkDong} onRows={setRkRows} onPick={pickRealtor} onDong={pickDong} onRealtor={openRt} ad={ads.realtor_top[0]} />}
    </>
  );

  return (
    <div className={"t2" + (phone ? " phone" : " desk")}>
      <TopBar phone={phone} favs={favs} session={!!session} user={session ? sessionName(session) : null} onMe={() => setMeOpen(true)} onGo={goComplex} onAddr={(lat, lng) => goTo(lat, lng, 4)} onLogin={() => setAskLogin(true)}
        statsOn={!!stats} safeOn={!!safe} onStats={() => { const was = !!stats; closeWins(); if (!was) setStats({ g: "price", i: "top" }); }} onSafe={() => { const was = !!safe; closeWins(); if (!was) setSafe("alert"); }} onFavDash={openFav} onPick={(c) => {
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
                  onClick={() => { setLayer(l.key); setSel(null); }}>{phone ? l.short : l.label}</button>
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
          <div className={"t2-zoom" + (phone ? " sh-" + sheet : "")}>
            <button onClick={() => mapRef.current?.setLevel(mapRef.current.getLevel() - 1)} aria-label="확대">+</button>
            <button onClick={() => mapRef.current?.setLevel(mapRef.current.getLevel() + 1)} aria-label="축소">−</button>
          </div>
          {/* 매물의뢰 — 절충안의 떠 있는 버튼. 세 갈래: 중개사에게 매물의뢰 · AI 상담사 · 내 요청 보기 */}
          {!phone && !stats && !safe && !ask && !fav && !rt && (
            <div className={"t2-fabwrap" + (sel || selJ ? " narrow" : "")}>
              {reqOpen && <ReqMenu onClose={() => setReqOpen(false)} onPick={openAsk} />}
              <button className="t2-fab" onClick={() => setReqOpen(!reqOpen)} aria-expanded={reqOpen}>매물의뢰</button>
            </div>
          )}
          {stats && <StatsWindow open={stats} onKey={setStats} phone={phone} onClose={() => setStats(null)}
            region={{ sido: region ? region.dong.slice(0, 2) + "00000000" : "", sgg: region?.sgg || "", dong: "" }}
            onPick={(no, name) => { setStats(null); goComplex(no, name); }}
            onMapLayer={() => { setStats(null); setLayer("price"); setPm("tx"); }}
            onSafe={() => { setStats(null); setSafe("jeonse"); }} ad={ads.stats_band[0]} />}
          {safe && <SafeWindow tab={safe} onTab={setSafe} phone={phone} onClose={() => setSafe(null)} session={session}
            at={selJ ? { lat: selJ.lat, lng: selJ.lng, name: selJ.name } : null} onLogin={() => setAskLogin(true)} />}
          {ask && <AskWindow tab={ask} onTab={setAsk} phone={phone} onClose={() => setAsk(null)} session={session} token={init.proposals || undefined}
            region={{ sido: region ? region.dong.slice(0, 2) + "00000000" : "", sgg: region?.sgg || "", dong: region?.dong || "" }}
            onGo={(path, text) => {
              const m = /^\/complex\/(\d+)/.exec(path);
              if (m) { setAsk(null); goComplex(m[1], text || ""); }
              else if (/^\/realtor\//.test(path)) openRt(decodeURIComponent(path.split("/")[2] || "").split("?")[0]);
              else if (path.startsWith("/my/favorites")) openFav();
              else if (path.startsWith("/special-deals")) { closeWins(); setLayer("deals"); setFlt((f) => ({ ...f, trade: "A1", sp: "owner" })); }
              else if (path.startsWith("/quick-deals") || path.startsWith("/today")) { closeWins(); setLayer("deals"); }
              else if (path.startsWith("/tx-map")) { closeWins(); setLayer("price"); setPm("tx"); }
              else if (path.startsWith("/tx-stats/record-high")) { closeWins(); setStats({ g: "price", i: "rh" }); }
              else if (path.startsWith("/tx-stats") || path.startsWith("/changes") || path.startsWith("/overview")) { closeWins(); setStats({ g: "price", i: "top" }); }
              else if (path.startsWith("/jeonse-check")) { closeWins(); setSafe("jeonse"); }
              else if (path.startsWith("/buy-calculator")) { closeWins(); setSafe("calc"); }
              else if (path.startsWith("/realtors")) { closeWins(); setLayer("realtor"); }
              else if (path.startsWith("/ai")) openAsk("ai");
              else if (path.startsWith("/settings")) setMeOpen(true);
              else window.open(SITE + path, "_blank", "noreferrer");   // 중개사라운지·약관 등 지도 밖 문서만
            }} />}
          {fav && <FavWindow phone={phone} session={session} onClose={() => setFav(false)} onRemoved={(no) => setFavs((o) => (o || []).filter((f) => f.complex_no !== no))}
            onGo={(no, name, tab) => { setFav(false); goComplex(no, name, tab); }} />}
          {rt && <RealtorWindow id={rt} phone={phone} session={session} onClose={() => setRt(null)} onMe={() => setMeOpen(true)}
            onGo={(no, name) => { setRt(null); goComplex(no, name); }} />}
          {!phone && sel && <aside className="t2-drawer"><ComplexDrawer cx={sel} initialTab={drawerTab} onClose={() => setSel(null)} onPick={(c) => pickComplex(c, true)} onRealtor={openRt} onMine={() => openAsk("mine")} adTop={ads.realtor_top[0]} adLife={ads.info_life[0]}
            fav={favs ? favs.some((f) => f.complex_no === sel.complex_no) : null} onFav={() => toggleFav(sel)} /></aside>}
          {!phone && !sel && selJ && <aside className="t2-drawer"><JibunDrawer j={selJ} months={Math.round(pw / 30)} onClose={() => setSelJ(null)} /></aside>}
          {meOpen && session && <MeModal session={session} onClose={() => setMeOpen(false)} onLogout={() => logout()} />}
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
                {sel ? <ComplexDrawer cx={sel} initialTab={drawerTab} onClose={() => setSel(null)} onPick={(c) => pickComplex(c, true)} onRealtor={openRt} onMine={() => openAsk("mine")} adTop={ads.realtor_top[0]} adLife={ads.info_life[0]}
                  fav={favs ? favs.some((f) => f.complex_no === sel.complex_no) : null} onFav={() => toggleFav(sel)} />
                  : selJ ? <JibunDrawer j={selJ} months={Math.round(pw / 30)} onClose={() => setSelJ(null)} /> : panel}
              </div>
            </section>
          )}
        </main>
      </div>
      {!phone && <FootBar onLegal={setLegal} onAd={() => setAdInfo(true)} />}
      {legal && <LegalModal kind={legal} onClose={() => setLegal(null)} />}
      {adInfo && <AdInfoModal onClose={() => setAdInfo(false)} />}
      {phone && (
        <nav className="t2-tabbar">
          <button className={!stats && !safe && !ask && !fav && !rt ? "on" : ""} onClick={closeWins}>지도</button>
          <button className={stats ? "on" : ""} onClick={() => { closeWins(); setStats({ g: "price", i: "top" }); }}>통계</button>
          <button className={"req" + (ask ? " on" : "")} onClick={() => setReqOpen(!reqOpen)}>의뢰</button>
          <button className={safe ? "on" : ""} onClick={() => { closeWins(); setSafe("alert"); }}>안심</button>
          <button onClick={() => setMore(!more)}>더보기</button>
          {reqOpen && <div className="t2-more req" onClick={() => setReqOpen(false)}><ReqMenu onClose={() => setReqOpen(false)} onPick={openAsk} /></div>}
          {more && (
            <div className="t2-more" onClick={() => setMore(false)}>
              {favs && favs.length > 0 && favs.map((f) => <button key={f.complex_no} onClick={() => goComplex(f.complex_no, f.complex_name)}>관심단지 · {f.complex_name}</button>)}
              {session && <button onClick={openFav}>관심단지 대시보드</button>}
              {!session ? <button onClick={() => setAskLogin(true)}>로그인 · 관심단지</button>
                : <button onClick={() => setMeOpen(true)}>{sessionName(session)} · 내 정보</button>}
              <a href={`${SITE}/lounge`} target="_blank" rel="noreferrer">중개사라운지</a>
              <FootNote onLegal={(k) => { setMore(false); setLegal(k); }} onAd={() => { setMore(false); setAdInfo(true); }} />
            </div>
          )}
        </nav>
      )}
    </div>
  );
}

// ── 매물의뢰 갈래 메뉴 ───────────────────────────────
// 세 갈래 모두 지도 위 매물의뢰 창(Ask.tsx)에서 열린다. 단지·사무소에서 여는 한 곳 지정 요청은 서랍의 RequestModal.
function ReqMenu({ onClose, onPick }: { onClose: () => void; onPick: (t: AskTab) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const h = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) onClose(); };
    const t = setTimeout(() => document.addEventListener("mousedown", h), 0);
    return () => { clearTimeout(t); document.removeEventListener("mousedown", h); };
  }, [onClose]);
  return (
    <div className="t2-reqmenu" ref={ref}>
      <button onClick={() => onPick("req")}><b>중개사에게 매물의뢰</b><span>지역·예산·조건을 적으면 동네 중개사가 매물을 찾아 제안해요</span></button>
      <button onClick={() => onPick("ai")}><b>AI 상담사</b><span>"강남 30평대 급매 찾아줘"처럼 말로 물어보기</span></button>
      <button onClick={() => onPick("mine")}><b>내 요청 보기</b><span>보낸 의뢰와 중개사 제안 확인</span></button>
    </div>
  );
}

// ── 상단 바 ─────────────────────────────────────────
function TopBar({ phone, onPick, favs, session, user, onMe, onGo, onAddr, onLogin, statsOn, safeOn, onStats, onSafe, onFavDash }: { phone: boolean; onPick: (c: Cx) => void; favs: { complex_no: string; complex_name: string }[] | null;
  session: boolean; user: string | null; onMe: () => void; onGo: (no: string, name: string) => void; onAddr: (lat: number, lng: number) => void; onLogin: () => void;
  statsOn: boolean; safeOn: boolean; onStats: () => void; onSafe: () => void; onFavDash: () => void }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<any[]>([]);
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
          {/* 지도 밖 기능 셋(절충안): 안심 · 통계 · 중개사라운지. 안심·통계는 지도 위 창 */}
          <button className={"t2-utilbtn" + (safeOn ? " on" : "")} onClick={onSafe}>안심</button>
          <button className={"t2-utilbtn" + (statsOn ? " on" : "")} onClick={onStats}>통계</button>
          <span className="t2-dd" onMouseLeave={() => setFavOpen(false)}>
            <button className={"t2-favbtn" + (favs?.length ? " has" : "")} onClick={() => setFavOpen(!favOpen)} aria-expanded={favOpen}>관심단지{favs?.length ? ` ${favs.length}` : ""}</button>
            {favOpen && (
              <span className="t2-ddm favs">
                {!session ? <button onClick={() => { setFavOpen(false); onLogin(); }}>로그인하고 관심단지 담기</button>
                  : !favs?.length ? <span className="t2-ddm-note">단지 서랍의 하트를 누르면 여기에 모여요(최대 20곳)</span>
                  : favs.map((f) => <button key={f.complex_no} onClick={() => { setFavOpen(false); onGo(f.complex_no, f.complex_name); }}>{f.complex_name}</button>)}
                {session && <button className="dash" onClick={() => { setFavOpen(false); onFavDash(); }}>관심단지 대시보드</button>}
              </span>
            )}
          </span>
          <a className="lounge" href={`${SITE}/lounge`} target="_blank" rel="noreferrer">중개사라운지</a>
          {session
            ? <button className="t2-loginbtn on" onClick={onMe} title="내 정보"><span>{user}</span>내 정보</button>
            : <button className="t2-loginbtn" onClick={onLogin}>로그인</button>}
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
  // 여러 개 고르는 항목(방·욕실·층·방향·시설): 체크 모양, 하나도 안 고르면 전체
  const multi = (o: { k: string; l: string }, cur: string[], f: (v: string[]) => void) => {
    const on = cur.includes(o.k);
    return <button key={o.k} className={on ? "on chk" : "chk"} onClick={() => f(on ? cur.filter((x) => x !== o.k) : [...cur, o.k])}><i />{o.l}</button>;
  };
  const nOr = (xs: string[], one: (k: string) => string, word: string) => (xs.length === 0 ? "" : xs.length === 1 ? one(xs[0]) : `${word} ${xs.length}`);
  const cxParts = [hhL && hhL !== "전체" ? hhL : "", flt.bld ? `${flt.bld}동+` : "", flt.park ? `주차 ${flt.park}대+` : "", flt.far ? `용적률 ${flt.far}%-` : ""].filter(Boolean);
  const cxLabel = cxParts.length === 0 ? "단지정보" : cxParts.length === 1 ? cxParts[0] : `단지정보 ${cxParts.length}`;
  const condParts = [flt.verify === "owner" ? "집주인 확인" : flt.verify === "doc" ? "확인 매물" : "", flt.confirm ? CONFIRM_OPTS.find((o) => o.v === flt.confirm)!.l : "", flt.down ? "가격 내림" : "", flt.only ? `급매 ${Math.round(flt.disc * 100)}%+` : ""].filter(Boolean);
  const condLabel = condParts.length === 0 ? "매물보기 조건" : condParts.length === 1 ? condParts[0] : `조건 ${condParts.length}`;
  const rbParts = [nOr(flt.rooms, (k) => ROOM_OPTS.find((o) => o.k === k)!.l, "방"), nOr(flt.baths, (k) => BATH_OPTS.find((o) => o.k === k)!.l, "욕실")].filter(Boolean);
  const rbLabel = rbParts.length === 0 ? "방/욕실" : rbParts.join(" · ");
  const fdParts = [nOr(flt.floor, (k) => FLOOR_OPTS.find((o) => o.k === k)!.l, "층"), nOr(flt.dirs, (k) => k, "방향")].filter(Boolean);
  const fdLabel = fdParts.length === 0 ? "층/방향" : fdParts.join(" · ");
  const ctParts = [flt.sp ? SPECIAL_KINDS.find((x) => x.k === flt.sp)?.l || "" : "", flt.loan === "none" ? "융자금 없음" : flt.loan === "low" ? "융자금 적음" : ""].filter(Boolean);
  const ctLabel = ctParts.length === 0 ? "계약조건" : ctParts.join(" · ");
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
      <Dd id="cx" open={open} setOpen={setOpen} label={cxLabel} active={!!flt.hmin || !!flt.hmax || !!flt.bld || !!flt.park || !!flt.far}>
        <span className="t2-ddm-in cols" onClick={(e) => e.stopPropagation()}>
          <span className="t2-ddm-col"><small>세대수</small>{HH_OPTS.map((o) => opt(o, flt.hmin === o.a && flt.hmax === o.b, () => set({ hmin: o.a, hmax: o.b })))}</span>
          <span className="t2-ddm-col"><small>동수</small>{BLD_OPTS.map((o) => opt(o, flt.bld === o.v, () => set({ bld: o.v })))}</span>
          <span className="t2-ddm-col"><small>주차</small>{PARK_OPTS.map((o) => opt(o, flt.park === o.v, () => set({ park: o.v })))}</span>
          <span className="t2-ddm-col"><small>용적률</small>{FAR_OPTS.map((o) => opt(o, flt.far === o.v, () => set({ far: o.v })))}</span>
        </span>
      </Dd>
      <Dd id="walk" open={open} setOpen={setOpen} label={flt.walk ? `역 ${flt.walk}분` : "역세권"} active={!!flt.walk}>
        {WALK_OPTS.map((o) => opt(o, flt.walk === o.v, () => set({ walk: o.v })))}
      </Dd>
      <Dd id="cond" open={open} setOpen={setOpen} label={condLabel} active={!!flt.verify || !!flt.confirm || flt.down || flt.only}>
        <span className="t2-ddm-in cols" onClick={(e) => e.stopPropagation()}>
          <span className="t2-ddm-col"><small>확인</small>
            {opt({ l: "전체" }, !flt.verify, () => set({ verify: "" }))}{opt({ l: "집주인 확인 매물" }, flt.verify === "owner", () => set({ verify: "owner" }))}{opt({ l: "확인 매물(서류·집주인)" }, flt.verify === "doc", () => set({ verify: "doc" }))}</span>
          <span className="t2-ddm-col"><small>확인일</small>{CONFIRM_OPTS.map((o) => opt(o, flt.confirm === o.v, () => set({ confirm: o.v })))}</span>
          <span className="t2-ddm-col"><small>가격</small>
            <button className={flt.down ? "on chk" : "chk"} onClick={() => set({ down: !flt.down })}><i />가격 내린 매물</button>
            <button className={flt.only ? "on chk" : "chk"} onClick={() => set({ only: !flt.only })}><i />급매만(실거래 평균 대비)</button>
            {flt.only && [0.03, 0.05, 0.1].map((v) => opt({ l: `${Math.round(v * 100)}% 이상 싼` }, flt.disc === v, () => set({ disc: v })))}</span>
        </span>
      </Dd>
      <Dd id="rb" open={open} setOpen={setOpen} label={rbLabel} active={flt.rooms.length > 0 || flt.baths.length > 0}>
        <span className="t2-ddm-in cols" onClick={(e) => e.stopPropagation()}>
          <span className="t2-ddm-col"><small>방</small>{ROOM_OPTS.map((o) => multi(o, flt.rooms, (v) => set({ rooms: v })))}</span>
          <span className="t2-ddm-col"><small>욕실</small>{BATH_OPTS.map((o) => multi(o, flt.baths, (v) => set({ baths: v })))}</span>
        </span>
      </Dd>
      <Dd id="fd" open={open} setOpen={setOpen} label={fdLabel} active={flt.floor.length > 0 || flt.dirs.length > 0}>
        <span className="t2-ddm-in cols" onClick={(e) => e.stopPropagation()}>
          <span className="t2-ddm-col"><small>층</small>{FLOOR_OPTS.map((o) => multi(o, flt.floor, (v) => set({ floor: v })))}</span>
          <span className="t2-ddm-col"><small>방향</small>{DIR_OPTS.map((o) => multi(o, flt.dirs, (v) => set({ dirs: v })))}</span>
        </span>
      </Dd>
      <Dd id="ct" open={open} setOpen={setOpen} label={ctLabel} active={!!flt.sp || !!flt.loan}>
        <span className="t2-ddm-in cols" onClick={(e) => e.stopPropagation()}>
          {flt.trade === "A1" && <span className="t2-ddm-col"><small>특수조건</small>{opt({ l: "전체" }, !flt.sp, () => set({ sp: "" }))}{SPECIAL_KINDS.map((x) => opt({ l: `${x.l} — ${x.h}` }, flt.sp === x.k, () => set({ sp: x.k })))}</span>}
          <span className="t2-ddm-col"><small>융자금</small>{opt({ l: "전체" }, !flt.loan, () => set({ loan: "" }))}{opt({ l: "융자금 없는 매물" }, flt.loan === "none", () => set({ loan: "none" }))}{opt({ l: "융자금 없거나 적은 매물" }, flt.loan === "low", () => set({ loan: "low" }))}</span>
        </span>
      </Dd>
      <Dd id="tg" open={open} setOpen={setOpen} label={flt.tags.length ? (flt.tags.length === 1 ? TAG_OPTS.find((t) => t.k === flt.tags[0])!.l : `시설 ${flt.tags.length}`) : "시설"} active={flt.tags.length > 0}>
        <span className="t2-ddm-in" onClick={(e) => e.stopPropagation()}>{TAG_OPTS.map((o) => multi(o, flt.tags, (v) => set({ tags: v })))}</span>
      </Dd>
      {dirty && <button className="t2-freset" onClick={() => onChange(FLT0)}>초기화</button>}
    </div>
  );
}

// ── 매물찾기: 위 2/3 급매, 아래 1/3 콕집 매물 ─────────────────
function DealsPanel({ region, inView, onPick, zoomedOut, onRequest, ad }: { region: Region | null; inView: Cx[]; onPick: (c: Cx) => void; zoomedOut: boolean; onRequest: () => void; ad?: Ad }) {
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
        {ad && <AdRow ad={ad} onGo={(no, name) => onPick({ complex_no: no, name, lat: 0, lng: 0 })} />}
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
          <button onClick={onRequest}>이 동네 매물 요청하기</button>
          <a className="ghost" href={`${SITE}/lounge`} target="_blank" rel="noreferrer">중개사 · 매물 올리기</a>
        </div>
      </section>
    </div>
  );
}

// ── 시세분석 ───────────────────────────────────────
const eok = (v: number) => (v >= 1e8 ? `${(v / 1e8).toFixed(1)}억` : `${Math.round(v / 1e4).toLocaleString()}만`);
const VOL_MIN = 10;   // 거래량 변동률을 보여 줄 최소 건수(두 기간 모두)
const volOk = (a: { n: number; n_prev?: number | null; change?: number | null }) => a.change != null && (a.n ?? 0) >= VOL_MIN && (a.n_prev ?? 0) >= VOL_MIN;
const signPct = (v: number | null | undefined) => (v == null ? "-" : `${v > 0 ? "+" : ""}${v.toFixed(1)}%`);
const chgCls = (v: number | null | undefined) => (v == null ? "flat" : v > 0.5 ? "up" : v < -0.5 ? "down" : "flat");

// 버블 한 칸의 글자·색. 변동률 칩(실거래가·호가·거래량)은 빨강 상승/파랑 하락, 갭은 전세가율 색(높을수록 진함).
function bubble(m: PriceMetric, a: Agg): { cls: string; main: string; sub: string } {
  if (m === "tx") return { cls: chgCls(a.change), main: signPct(a.change), sub: `${Math.round((a.ppy ?? 0) / 1e4).toLocaleString()}만/평` };
  if (m === "hoga") return { cls: chgCls(a.change), main: signPct(a.change), sub: `매물 ${a.n.toLocaleString()}건` };
  // 거래량: 두 기간 모두 VOL_MIN 건 이상일 때만 %(표본이 적으면 +200%·-100% 같은 극단값이 되므로), 미달이면 '전→지금 건'을 회색으로
  if (m === "vol") return volOk(a) ? { cls: chgCls(a.change), main: signPct(a.change), sub: `${a.n}건 (전 ${a.n_prev ?? 0})` }
    : { cls: "flat", main: `${a.n_prev ?? 0}→${a.n}건`, sub: `${VOL_MIN}건 미만` };
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
function RecordHighPanel({ rows, region, win, onWin, loading, onMetric, onPick, onStats }: { rows: RH[]; region: Region | null; win: number; onWin: (d: number) => void; loading: boolean; onStats: () => void;
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
      <button className="t2-stat-link" onClick={onStats}>{region ? `${region.sggName} ` : ""}신고가 통계 전체 보기</button>
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
    </div>
  );
}

function PricePanel({ region, agg, level, metric, onMetric, win, onWin, loading, meta, onPick, onStats }: {
  region: Region | null; agg: Agg[]; level: number; metric: PriceMetric; onMetric: (m: PriceMetric) => void;
  win: number; onWin: (d: number) => void; loading: boolean; meta: { snapshot?: string; baseline?: string }; onPick: (c: Cx) => void; onStats: () => void;
}) {
  const isCx = level <= 4;
  const unit = level >= 7 ? "구별" : isCx ? "단지별" : "동별";
  const rows = useMemo(() => {
    const r = [...agg];
    if (metric === "gap") r.sort((a, b) => (b.rate ?? 0) - (a.rate ?? 0));
    else if (metric === "vol") r.sort((a, b) => (Number(volOk(b)) - Number(volOk(a))) || ((volOk(a) ? (b.change ?? -999) - (a.change ?? -999) : b.n - a.n)));   // %가 있는 곳 먼저, 나머지는 건수순
    else r.sort((a, b) => (b.change ?? -999) - (a.change ?? -999));
    return r;
  }, [agg, metric]);
  const m = METRICS.find((x) => x.k === metric)!;
  // 기간 설명 — 신고 기한(계약 후 30일)을 지표마다 다르게 다룬다.
  const note =
    metric === "tx" ? <>아파트 매매, 계약일 기준 최근 {win}일 vs 그 전 {win}일 평당가. 가격 평균은 신고 지연에 둔감해 오늘까지 세되, 최근 {REPORT_LAG}일 계약은 신고가 진행 중(약 70% 반영). <span className="up">빨강 상승</span> · <span className="down">파랑 하락</span></>
    : metric === "vol" ? <>신고 기한({REPORT_LAG}일)이 지난 계약만 셉니다: {REPORT_LAG}일 전부터 거꾸로 {win}일 vs 그 전 {win}일. 최근 {REPORT_LAG}일 계약은 '신고 중'으로 따로 — 지금 세면 30%쯤 모자라 보이기 때문. 두 기간 모두 {VOL_MIN}건 이상일 때만 %로, 미달이면 건수로 보여요.</>
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
      <button className="t2-stat-link" onClick={onStats}>{region ? `${region.sggName} ` : "이 지역 "}통계 전체 보기 (표·그래프)</button>
    </div>
  );
}

// ── 중개사랭킹 ─────────────────────────────────────
type Scope = "dong" | "gu" | "sido" | "nat";
type Opt = { code: string; name: string };
// 매물 범위 — 운영 우리동네 중개사 페이지와 같은 6종(by-dong·by-sido·national 의 scope=)
const MSCOPES: [string, string][] = [["complex", "단지형 (아파트·오피)"], ["house", "주택 (빌라·단독)"], ["comm", "상가·사무실"], ["building", "빌딩·건물"], ["land", "토지·공장"], ["all", "전체"]];
function RealtorPanel({ region, dong, onRows, onPick, onDong, onRealtor, ad }: { region: Region | null; dong: Opt | null;
  onRows: (rows: (Rk & { rank: number })[]) => void; onPick: (r: Rk) => void; onDong: (d: Opt, path: string) => void; onRealtor: (id: string) => void; ad?: Ad }) {
  const [scope, setScope] = useState<Scope>("dong");
  const [mode, setMode] = useState<"dong" | "name">("dong");   // 찾는 방법: 동네로 / 사무소 이름으로(운영 페이지와 동일)
  const [mscope, setMscope] = useState("complex");
  const [sort, setSort] = useState<"listings" | "staff" | "tenure">("listings");
  const [rows, setRows] = useState<Rk[] | null>(null);
  const [apiName, setApiName] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  // 지역 고르기(시·도 → 시·군·구 → 읍·면·동) — 운영과 같은 목록 API. 기본값은 지도가 보는 곳.
  const [sidos, setSidos] = useState<Opt[]>([]);
  const [sggs, setSggs] = useState<Opt[]>([]);
  const [dongs, setDongs] = useState<Opt[]>([]);
  const [pSido, setPSido] = useState("");
  const [pSgg, setPSgg] = useState("");
  useEffect(() => { getJson(`/stats/changes/sido-list`).then((j) => setSidos(j.items || [])).catch(() => {}); }, []);
  useEffect(() => { if (region && !dong) { setPSido(region.dong.slice(0, 2) + "00000000"); setPSgg(region.sgg); } }, [region?.sgg, dong]);   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (!pSido) return; getJson(`/stats/sigungu-list?sido=${pSido}`).then((j) => setSggs(j.items || [])).catch(() => setSggs([])); }, [pSido]);
  useEffect(() => { if (!pSgg) { setDongs([]); return; } getJson(`/stats/dong-list?sigungu=${pSgg}`).then((j) => setDongs(j.items || [])).catch(() => setDongs([])); }, [pSgg]);
  const sidoName = sidos.find((s) => s.code === pSido)?.name || region?.sidoName || "시·도";
  const sggName = sggs.find((s) => s.code === pSgg)?.name || (pSgg && pSgg === region?.sgg ? region?.sggName : "") || "시·군·구";
  const code = dong?.code || region?.dong;
  const name = dong?.name || region?.dongName || apiName;
  // 사무소 이름 검색(/stats/realtors/search)
  const [q, setQ] = useState("");
  const [qRes, setQRes] = useState<any[] | null>(null);
  useEffect(() => {
    const t = q.trim();
    if (!t) { setQRes(null); return; }
    const id = window.setTimeout(() => {
      getJson(`/stats/realtors/search?q=${encodeURIComponent(t)}&limit=40`).then((j) => setQRes(j.items || [])).catch(() => setQRes([]));
    }, 300);
    return () => window.clearTimeout(id);
  }, [q]);

  useEffect(() => {
    setRows(null);
    if (scope === "dong" && code) {
      getJson(`/stats/realtors/by-dong?cortar=${code}&scope=${mscope}&limit=200`).then((j) => { setApiName(j.dong_name || ""); setRows(j.items || []); }).catch(() => setRows([]));
    } else if (scope === "gu" && pSgg) {
      // 구 범위 = by-dong 에 시군구 코드(xxxxx00000)를 주면 그 구에 소재한 사무소 전체
      getJson(`/stats/realtors/by-dong?cortar=${pSgg}&scope=${mscope}&limit=300`).then((j) => { setApiName(j.dong_name || ""); setRows(j.items || []); }).catch(() => setRows([]));
    } else if (scope === "sido" && sidoName) {
      getJson(`/stats/realtors/by-sido?limit=50&scope=${mscope}`).then((j) => {
        const g = j.groups?.[sidoName] || [];
        setRows(g.map((r: any) => ({ ...r, listings: r.count })));
      }).catch(() => setRows([]));
    } else if (scope === "nat") {
      getJson(`/stats/realtors/national?limit=50&scope=${mscope}`).then((j) =>
        setRows((j.items || []).map((r: any) => ({ ...r, listings: r.count })))).catch(() => setRows([]));
    } else setRows([]);
  }, [scope, code, sidoName, mscope, pSgg]);   // eslint-disable-line react-hooks/exhaustive-deps

  const sorted = useMemo(() => {
    const xs = [...(rows || [])];
    if (sort === "staff") xs.sort((a, b) => (b.staff_count ?? 0) - (a.staff_count ?? 0));
    else if (sort === "tenure") xs.sort((a, b) => (b.tenure_years ?? 0) - (a.tenure_years ?? 0));
    else xs.sort((a, b) => b.listings - a.listings);
    return xs.slice(0, 50);
  }, [rows, sort]);
  const max = Math.max(1, ...sorted.map((r) => r.listings));
  const title = scope === "dong" ? name : scope === "gu" ? sggName : scope === "sido" ? sidoName : "전국";
  // 지도 핀은 동 랭킹만(시도·전국은 사무소가 너무 흩어져 있어 목록만)
  useEffect(() => { onRows(scope === "dong" && mode === "dong" ? sorted.map((r, i) => ({ ...r, rank: i + 1 })) : []); }, [sorted, scope, mode]);   // eslint-disable-line react-hooks/exhaustive-deps
  const opt = (l: string, on: boolean, f: () => void) => <button key={l} className={on ? "on" : ""} onClick={f}>{l}</button>;
  const msLabel = MSCOPES.find((m) => m[0] === mscope)?.[1] || "매물 범위";

  return (
    <div className="t2-pad">
      <div className="t2-modes">
        <button className={mode === "dong" ? "on" : ""} onClick={() => { setMode("dong"); setQ(""); }}>우리 동네로</button>
        <button className={mode === "name" ? "on" : ""} onClick={() => setMode("name")}>사무소 이름으로</button>
      </div>
      {mode === "name" ? (
        <>
          <div className="t2-nsearch">
            <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="중개사무소 이름 (예: 래미안, 자이…)" />
            {q && <button onClick={() => setQ("")} aria-label="지우기">×</button>}
          </div>
          {!q.trim() ? <p className="t2-empty">중개사무소 이름을 입력하면 전국에서 찾아요.</p>
            : qRes == null ? <Skel />
            : qRes.length === 0 ? <p className="t2-empty">일치하는 중개사무소가 없어요.</p> : (
              <>
                <p className="t2-note">'{q.trim()}' {qRes.length}곳 · 단지형 매물 수순</p>
                <ol className="t2-rank">
                  {qRes.map((r, i) => (
                    <li key={(r.realtor_id || r.realtor_name) + i}>
                      <a href={`?rt=${encodeURIComponent(r.realtor_id || "")}`} onClick={(e) => { e.preventDefault(); onRealtor(r.realtor_id || ""); }}>
                        <span className="n">{i + 1}</span>
                        <span className="o"><b>{r.realtor_name || "공인중개사"}</b>
                          <em>{[r.location, r.representative ? `대표 ${r.representative}` : "", r.staff_count ? `직원 ${r.staff_count}명` : "", r.established_year ? `${String(r.established_year).slice(0, 4)}년 개업` : ""].filter(Boolean).join(" · ")}</em></span>
                        <span className="bm" />
                        <span className="c">{(r.count || 0).toLocaleString()}</span>
                      </a>
                    </li>
                  ))}
                </ol>
              </>
            )}
        </>
      ) : (
        <>
          <div className="t2-seg">
            {([["dong", "동"], ["gu", "구"], ["sido", "시도"], ["nat", "전국"]] as [Scope, string][]).map(([k, l]) => (
              <button key={k} className={scope === k ? "on" : ""} onClick={() => setScope(k)}>{l}</button>
            ))}
          </div>
          <div className="t2-rsel">
            {scope !== "nat" && (
              <Dd id="sido" open={open} setOpen={setOpen} label={sidoName} active={false}>
                {sidos.map((s) => opt(s.name, s.code === pSido, () => { setPSido(s.code); setPSgg(""); }))}
              </Dd>
            )}
            {(scope === "dong" || scope === "gu") && (
              <Dd id="sgg" open={open} setOpen={setOpen} label={sggName} active={false}>
                {sggs.length ? sggs.map((s) => opt(s.name, s.code === pSgg, () => setPSgg(s.code))) : <span className="t2-ddm-note">시·도를 먼저 고르세요</span>}
              </Dd>
            )}
            {scope === "dong" && (
              <Dd id="dong" open={open} setOpen={setOpen} label={name || "읍·면·동"} active={!!dong}>
                {dongs.length ? dongs.map((d) => opt(d.name, d.code === code, () => onDong(d, `${sidoName} ${sggName} ${d.name}`))) : <span className="t2-ddm-note">시·군·구를 먼저 고르세요</span>}
              </Dd>
            )}
            <Dd id="ms" open={open} setOpen={setOpen} label={msLabel} active={mscope !== "complex"}>
              {MSCOPES.map(([v, l]) => opt(l, mscope === v, () => setMscope(v)))}
            </Dd>
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
            {scope === "dong" ? `기준: 이 동 ${msLabel.replace(/ \(.*\)/, "")} 매물 수 · 지도의 동을 눌러도 바뀌어요` : `기준: ${msLabel.replace(/ \(.*\)/, "")} 매물 수`}
          </p>
          {ad && (scope === "dong" || scope === "gu") && <AdRow ad={ad} onRealtor={onRealtor} />}
          {rows == null ? <Skel /> : sorted.length === 0 ? <p className="t2-empty">랭킹 자료가 없어요.</p> : (
            <ol className="t2-rank">
              {sorted.map((r, i) => (
                <li key={r.realtor_id + i} className={i === 0 ? "top1" : ""}>
                  <a href={`?rt=${encodeURIComponent(r.realtor_id)}`}
                    onClick={(e) => { e.preventDefault(); if (scope === "dong") onPick(r); else onRealtor(r.realtor_id); }}>
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
          {scope === "dong" && <p className="t2-foot">줄을 누르면 지도의 사무소 핀이 열려요. 같은 건물의 사무소는 한 핀에 묶여요. 네이버 프로필 좌표가 없는 곳은 등록 주소로 찾아 찍어요.</p>}
        </>
      )}
    </div>
  );
}
