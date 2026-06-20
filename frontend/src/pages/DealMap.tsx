import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Flame } from "lucide-react";
import { loadKakao, wonShort, escapeHtml } from "../lib/kakaomap";
import MapRegionPicker from "../components/MapRegionPicker";

const API_BASE = import.meta.env.VITE_API_BASE;

type Deal = {
  complex_no: string; complex_name: string; lat: number; lng: number;
  area_name: string; area1_m2: number | null;
  n_listings: number; asking_min: number; avg_real: number;
  n_real: number; discount: number; // 음수 (예: -0.12)
};

type Filters = { trade: "A1" | "B1"; disc: number; days: number; pyeong: number | null };

const PYEONG_OPTS: { v: number | null; label: string }[] = [
  { v: null, label: "전체평형" }, { v: 10, label: "10평대" }, { v: 20, label: "20평대" },
  { v: 30, label: "30평대" }, { v: 40, label: "40평+" },
];

const FLAME_SVG =
  `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="white" ` +
  `stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">` +
  `<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 ` +
  `.5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/></svg>`;

function dealPillHtml(d: Deal): string {
  const pct = Math.round(-d.discount * 100);
  const strong = d.discount <= -0.1;
  return (
    `<div class="dm-pill ${strong ? "dm-strong" : "dm-mid"}">` +
    `<span class="dm-ico">${FLAME_SVG}</span><b>${pct}%</b>` +
    `</div>`
  );
}

function dealTipHtml(d: Deal): string {
  const pct = Math.round(-d.discount * 100);
  return (
    `<div class="cx-tip">` +
    `<div class="cx-tip-name">${escapeHtml(d.complex_name)} <span style="font-weight:400;color:#888">${escapeHtml(d.area_name)}</span></div>` +
    `<div class="cx-tip-row">호가 <b>${wonShort(d.asking_min)}</b> ↓ 평균 실거래 <b>${wonShort(d.avg_real)}</b></div>` +
    `<div class="cx-tip-row"><b style="color:#e8590c">${pct}% 저렴</b> · 매물 <b>${d.n_listings}</b> · 거래 <b>${d.n_real}</b></div>` +
    `<div class="cx-tip-go">클릭 → 단지 상세</div>` +
    `</div>`
  );
}

export default function DealMap() {
  const mapEl = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const overlaysRef = useRef<any[]>([]);
  const filtersRef = useRef<Filters>({ trade: "A1", disc: 0.05, days: 90, pyeong: null });
  const loadRef = useRef<() => void>(() => {});
  const navigate = useNavigate();

  const [filters, setFilters] = useState<Filters>(filtersRef.current);
  const [status, setStatus] = useState<string>("");
  const [count, setCount] = useState<number | null>(null);

  const moveTo = (lat: number, lng: number, level: number) => {
    const map = mapRef.current;
    if (!map) return;
    map.setLevel(level);
    map.setCenter(new window.kakao.maps.LatLng(lat, lng));
  };

  useEffect(() => {
    filtersRef.current = filters;
    loadRef.current();
  }, [filters]);

  useEffect(() => {
    if (!API_BASE) { setStatus("VITE_API_BASE 미설정."); return; }
    let disposed = false;
    let debounce: ReturnType<typeof setTimeout>;

    loadKakao().then(() => {
      if (disposed || !mapEl.current) return;
      const kakao = window.kakao;
      const map = new kakao.maps.Map(mapEl.current, {
        center: new kakao.maps.LatLng(37.4979, 127.0276), level: 5,
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
        const f = filtersRef.current;
        setStatus("불러오는 중…");
        try {
          const q = `swlat=${sw.getLat()}&swlng=${sw.getLng()}&nelat=${ne.getLat()}&nelng=${ne.getLng()}`
            + `&trade_type=${f.trade}&min_discount=${f.disc}&days=${f.days}`
            + (f.pyeong != null ? `&pyeong=${f.pyeong}` : "");
          const r = await fetch(`${API_BASE}/stats/quick-deals-map?${q}`);
          const j = await r.json() as { too_wide?: boolean; count: number; items: Deal[] };
          if (disposed) return;
          clearOverlays();
          if (j.too_wide) {
            setCount(null);
            setStatus("지도를 더 확대하세요 (영역이 너무 넓음)");
            return;
          }
          for (const d of j.items) {
            const el = document.createElement("div");
            el.className = "cx-ov";
            el.innerHTML = dealPillHtml(d) + dealTipHtml(d);
            el.addEventListener("click", () => navigate(`/complex/${d.complex_no}`));
            const ov = new kakao.maps.CustomOverlay({
              position: new kakao.maps.LatLng(d.lat, d.lng),
              content: el, yAnchor: 1.0, clickable: true, zIndex: 1,
            });
            // 마우스 올린 핀(+툴팁)을 최상단으로 — 옆 핀 박스에 가리지 않게
            el.addEventListener("mouseenter", () => ov.setZIndex(10000));
            el.addEventListener("mouseleave", () => ov.setZIndex(1));
            ov.setMap(map);
            overlaysRef.current.push(ov);
          }
          setCount(j.count);
          setStatus(j.count === 0 ? "이 영역엔 조건에 맞는 급매가 없습니다" : "");
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
      loadRef.current = () => {};
      overlaysRef.current.forEach((o) => o.setMap(null));
      overlaysRef.current = [];
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const set = (patch: Partial<Filters>) => setFilters((f) => ({ ...f, ...patch }));

  return (
    <>
      <div className="map-head">
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, display: "inline-flex", alignItems: "center", gap: 6 }}>
          <Flame size={17} strokeWidth={2.4} style={{ color: "#d6336c" }} aria-hidden /> 급매찾기 (지도)
        </h2>
        <span className="muted" style={{ fontSize: 12 }}>
          최근 {filters.days}일 실거래 평균 대비 {Math.round(filters.disc * 100)}%↑ 저렴한 매물이 있는 단지
        </span>
        <span className="muted" style={{ fontSize: 12, marginLeft: "auto" }}>
          {count != null ? `${count}개 단지` : ""}{status && ` · ${status}`}
        </span>
      </div>

      <div className="map-toolbar">
        <MapRegionPicker onMove={moveTo} />
      </div>

      <div className="dm-filters">
        <div className="map-metric">
          <button className={filters.trade === "A1" ? "on" : ""} onClick={() => set({ trade: "A1" })}>매매</button>
          <button className={filters.trade === "B1" ? "on" : ""} onClick={() => set({ trade: "B1" })}>전세</button>
        </div>
        <span className="dm-sep" />
        <div className="map-metric">
          <button className={filters.disc === 0.05 ? "on" : ""} onClick={() => set({ disc: 0.05 })}>5%↑</button>
          <button className={filters.disc === 0.1 ? "on" : ""} onClick={() => set({ disc: 0.1 })}>10%↑</button>
        </div>
        <span className="dm-sep" />
        <div className="map-metric">
          <button className={filters.days === 90 ? "on" : ""} onClick={() => set({ days: 90 })}>90일</button>
          <button className={filters.days === 180 ? "on" : ""} onClick={() => set({ days: 180 })}>180일</button>
        </div>
        <span className="dm-sep" />
        <div className="map-metric">
          {PYEONG_OPTS.map((p) => (
            <button key={String(p.v)} className={filters.pyeong === p.v ? "on" : ""} onClick={() => set({ pyeong: p.v })}>
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <div ref={mapEl} className="map-canvas" />
    </>
  );
}
