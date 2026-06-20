import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { loadKakao, wonShort, escapeHtml } from "../lib/kakaomap";
import MapRegionPicker from "../components/MapRegionPicker";
import { Flame } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE;

type Complex = {
  complex_no: string; name: string; lat: number; lng: number;
  households: number | null; listings: number;
  c_sale: number; c_jeonse: number; c_wol: number;
  max_sale: number | null; max_tx: number | null;
};

// 집모양 SVG (이모지 대신 — OS 무관 동일 렌더). 일반=브랜드블루, 급매=분홍.
const houseSvg = (stroke: string) =>
  `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="${stroke}" ` +
  `stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">` +
  `<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M10 21v-6h4v6"/></svg>`;
const HOUSE_SVG = houseSvg("#1268d3");
const HOUSE_SVG_DEAL = houseSvg("#d6336c");

function pillHtml(cx: Complex, deal?: number): string {
  const cell = (label: string, n: number, cls: string) =>
    `<span class="cx-c ${cls}${n ? "" : " z"}">${label}<b>${n}</b></span>`;
  const tag = deal != null ? `<span class="cx-deal-tag">급매 ${Math.round(-deal * 100)}%↓</span>` : "";
  return (
    `<div class="cx-pill${deal != null ? " deal" : ""}">` +
    tag +
    `<span class="cx-pill-ico">${deal != null ? HOUSE_SVG_DEAL : HOUSE_SVG}</span>` +
    cell("매", cx.c_sale, "s") + cell("전", cx.c_jeonse, "j") + cell("월", cx.c_wol, "w") +
    `</div>`
  );
}

function tipHtml(cx: Complex, deal?: number): string {
  const dealName = deal != null ? `<span class="cx-tip-deal">급매</span> ` : "";
  const dealRow = deal != null
    ? `<div class="cx-tip-row" style="color:#d6336c;font-weight:700">실거래 평균보다 ${Math.round(-deal * 100)}% 저렴한 매물 있음</div>` : "";
  return (
    `<div class="cx-tip">` +
    `<div class="cx-tip-name">${dealName}${escapeHtml(cx.name)}</div>` +
    dealRow +
    `<div class="cx-tip-row">매매 <b>${cx.c_sale}</b> · 전세 <b>${cx.c_jeonse}</b> · 월세 <b>${cx.c_wol}</b></div>` +
    `<div class="cx-tip-row">매매 최고호가 <b>${wonShort(cx.max_sale)}</b></div>` +
    `<div class="cx-tip-row">실거래 최고가 <b>${wonShort(cx.max_tx)}</b></div>` +
    `<div class="cx-tip-row">${cx.households != null ? `${cx.households.toLocaleString()}세대` : "세대수 -"}</div>` +
    `<div class="cx-tip-go">클릭 → 단지 상세</div>` +
    `</div>`
  );
}

type DealItem = { complex_no: string; complex_name: string; lat: number; lng: number;
  area_name: string; n_listings: number; asking_min: number; avg_real: number; n_real: number; discount: number };

function dealPinHtml(d: DealItem): string {
  const pct = Math.round(-d.discount * 100);
  return (
    `<div class="cx-pill deal">` +
    `<span class="cx-deal-tag">급매 ${pct}%↓</span>` +
    `<span class="cx-pill-ico">${HOUSE_SVG_DEAL}</span>` +
    `<span class="cx-c s">호가<b>${wonShort(d.asking_min)}</b></span>` +
    `</div>`
  );
}
function dealTipHtml(d: DealItem): string {
  const pct = Math.round(-d.discount * 100);
  return (
    `<div class="cx-tip">` +
    `<div class="cx-tip-name"><span class="cx-tip-deal">급매</span> ${escapeHtml(d.complex_name)} <span style="font-weight:400;color:#888">${escapeHtml(d.area_name)}</span></div>` +
    `<div class="cx-tip-row">호가 <b>${wonShort(d.asking_min)}</b> ↓ 평균 실거래 <b>${wonShort(d.avg_real)}</b></div>` +
    `<div class="cx-tip-row"><b style="color:#d6336c">${pct}% 저렴</b> · 매물 <b>${d.n_listings}</b> · 거래 <b>${d.n_real}</b></div>` +
    `<div class="cx-tip-go">클릭 → 단지 상세</div>` +
    `</div>`
  );
}

export default function MapView() {
  const mapEl = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const overlaysRef = useRef<any[]>([]);
  const navigate = useNavigate();
  const [sp] = useSearchParams();
  const initLat = parseFloat(sp.get("lat") || "");
  const initLng = parseFloat(sp.get("lng") || "");
  const hasInit = !isNaN(initLat) && !isNaN(initLng);
  const [status, setStatus] = useState<string>("");
  const [count, setCount] = useState<{ shown: number; total: number } | null>(null);
  const [dealOnly, setDealOnly] = useState(false);
  const dealOnlyRef = useRef(false);
  const loadRef = useRef<() => void>(() => {});

  const moveTo = (lat: number, lng: number, level: number) => {
    const map = mapRef.current;
    if (!map) return;
    map.setLevel(level);
    map.setCenter(new window.kakao.maps.LatLng(lat, lng));
  };

  useEffect(() => {
    if (!API_BASE) { setStatus("VITE_API_BASE 미설정."); return; }
    let disposed = false;
    let debounce: ReturnType<typeof setTimeout>;

    loadKakao().then(() => {
      if (disposed || !mapEl.current) return;
      const kakao = window.kakao;
      const map = new kakao.maps.Map(mapEl.current, {
        center: new kakao.maps.LatLng(hasInit ? initLat : 37.4979, hasInit ? initLng : 127.0276),
        level: hasInit ? 4 : 5,
      });
      mapRef.current = map;
      map.addControl(new kakao.maps.ZoomControl(), kakao.maps.ControlPosition.RIGHT);

      const clearOverlays = () => {
        overlaysRef.current.forEach((o) => o.setMap(null));
        overlaysRef.current = [];
      };

      const loadBounds = async () => {
        const b = map.getBounds();
        const sw = b.getSouthWest(), ne = b.getNorthEast();
        setStatus("불러오는 중…");
        const bbox = `swlat=${sw.getLat()}&swlng=${sw.getLng()}&nelat=${ne.getLat()}&nelng=${ne.getLng()}`;
        const CLUSTER_AT = 7;  // 이 레벨 이상(축소)이면 단지수 군집으로 묶음
        try {
          // ── 급매만 보기 → 급매 단지만 핀 표시 ──
          if (dealOnlyRef.current) {
            const rd = await fetch(`${API_BASE}/stats/quick-deals-map?${bbox}&min_discount=0.05`);
            const jd = await rd.json() as { too_wide?: boolean; items?: DealItem[] };
            if (disposed) return;
            clearOverlays();
            if (jd.too_wide) { setCount(null); setStatus("급매만 보기 — 확대하면 급매 단지가 보여요"); return; }
            const items = jd.items || [];
            for (const d of items) {
              const el = document.createElement("div");
              el.className = "cx-ov";
              el.innerHTML = dealPinHtml(d) + dealTipHtml(d);
              el.addEventListener("click", () => navigate(`/complex/${d.complex_no}`));
              const ov = new kakao.maps.CustomOverlay({
                position: new kakao.maps.LatLng(d.lat, d.lng), content: el, yAnchor: 1.0, clickable: true, zIndex: 1,
              });
              el.addEventListener("mouseenter", () => ov.setZIndex(10000));
              el.addEventListener("mouseleave", () => ov.setZIndex(1));
              ov.setMap(map);
              overlaysRef.current.push(ov);
            }
            setCount({ shown: items.length, total: items.length });
            setStatus(items.length ? "급매만 보기" : "이 영역에 급매가 없어요");
            return;
          }
          // ── 축소(레벨 높음) → 군집 표시 ──
          if (map.getLevel() >= CLUSTER_AT) {
            const rc = await fetch(`${API_BASE}/complexes/cluster?${bbox}`);
            const jc = await rc.json() as { cells: { lat: number; lng: number; count: number }[] };
            if (disposed) return;
            clearOverlays();
            let tot = 0;
            for (const cell of jc.cells) {
              tot += cell.count;
              const el = document.createElement("div");
              el.className = "cx-ov";
              const sz = cell.count >= 200 ? 56 : cell.count >= 50 ? 48 : cell.count >= 10 ? 42 : 36;
              el.innerHTML = `<div class="cx-cluster" style="width:${sz}px;height:${sz}px"><b>${cell.count.toLocaleString()}</b><span>단지</span></div>`;
              el.addEventListener("click", () => {
                map.setLevel(Math.max(1, map.getLevel() - 3));
                map.setCenter(new kakao.maps.LatLng(cell.lat, cell.lng));
              });
              const ov = new kakao.maps.CustomOverlay({
                position: new kakao.maps.LatLng(cell.lat, cell.lng),
                content: el, yAnchor: 0.5, xAnchor: 0.5, clickable: true, zIndex: 1,
              });
              ov.setMap(map);
              overlaysRef.current.push(ov);
            }
            setCount({ shown: jc.cells.length, total: tot });
            setStatus("축소 — 단지 군집(숫자=단지수). 클릭·확대하면 단지별로 보여요");
            return;
          }
          const [r, rd] = await Promise.all([
            fetch(`${API_BASE}/complexes/in-bounds?${bbox}&limit=600`),
            fetch(`${API_BASE}/stats/quick-deals-map?${bbox}&min_discount=0.05`).catch(() => null),
          ]);
          const j = await r.json() as { total: number; too_many: boolean; items: Complex[] };
          // 급매 단지 set (complex_no → 최대 할인율) — 매물지도에 급매 통합 표시
          const dealMap = new Map<string, number>();
          try {
            const jd = rd ? await rd.json() as { items?: { complex_no: string; discount: number }[] } : { items: [] };
            (jd.items || []).forEach((d) => dealMap.set(d.complex_no, d.discount));
          } catch { /* ignore */ }
          if (disposed) return;
          clearOverlays();
          for (const cx of j.items) {
            const deal = dealMap.get(cx.complex_no);
            const el = document.createElement("div");
            el.className = "cx-ov";
            el.innerHTML = pillHtml(cx, deal) + tipHtml(cx, deal);
            el.addEventListener("click", () => navigate(`/complex/${cx.complex_no}`));
            const ov = new kakao.maps.CustomOverlay({
              position: new kakao.maps.LatLng(cx.lat, cx.lng),
              content: el, yAnchor: 1.0, clickable: true, zIndex: 1,
            });
            // 마우스 올린 핀(+툴팁)을 최상단으로 — 옆 핀 박스에 가리지 않게
            el.addEventListener("mouseenter", () => ov.setZIndex(10000));
            el.addEventListener("mouseleave", () => ov.setZIndex(1));
            ov.setMap(map);
            overlaysRef.current.push(ov);
          }
          setCount({ shown: j.items.length, total: j.total });
          setStatus(j.too_many ? "너무 많아요 — 확대하면 정확해집니다" : "");
        } catch {
          setStatus("불러오기 실패");
        }
      };

      loadRef.current = loadBounds;
      kakao.maps.event.addListener(map, "idle", () => {
        clearTimeout(debounce);
        debounce = setTimeout(loadBounds, 250);
      });
      loadBounds();
    }).catch(() => setStatus("지도 로드 실패 — 카카오 콘솔에 도메인 등록 확인"));

    return () => {
      disposed = true;
      clearTimeout(debounce);
      overlaysRef.current.forEach((o) => o.setMap(null));
      overlaysRef.current = [];
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <>
      <div className="map-head">
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>지도보기</h2>
        <span className="muted" style={{ fontSize: 12, marginLeft: "auto" }}>
          {count ? `이 영역 ${count.total.toLocaleString()}개 단지${count.total > count.shown ? ` (상위 ${count.shown} 표시)` : ""}` : ""}
          {status && ` · ${status}`}
        </span>
      </div>
      <div className="map-toolbar">
        <MapRegionPicker onMove={moveTo} />
        <button type="button" className={`map-dealtoggle${dealOnly ? " on" : ""}`}
          onClick={() => { const v = !dealOnly; setDealOnly(v); dealOnlyRef.current = v; loadRef.current(); }}>
          <Flame size={13} strokeWidth={2.5} aria-hidden /> 급매만 보기
        </button>
      </div>
      <div ref={mapEl} className="map-canvas" />
    </>
  );
}
