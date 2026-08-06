// 랜딩 '우리동네 급매' 지도 — 카드 목록 위에 급매 단지 위치를 찍는다.
// 목록만 보면 어느 동네 물건인지 감이 안 와서, 위치를 먼저 보여주고 카드로 내려가게 한다.
// 좌표는 목록 API에 없어 /complexes/coords 로 따로 받는다(목록 페이로드를 키우지 않으려고).
import { useEffect, useMemo, useRef, useState } from "react";
import { loadKakao, wonShort, escapeHtml, attachMapControls } from "../lib/kakaomap";

const API = import.meta.env.VITE_API_BASE;

export type DealPin = {
  complex_no: string;
  complex_name: string;
  area_name?: string;
  asking_min?: number | null;
  discount_min?: number | null;   // 음수(-0.15 = 15% 싸요)
};

type Coord = { complex_no: string; lat: number; lng: number };

export default function DealMiniMap({ deals, onPick, height, onLocate }: {
  deals: DealPin[];
  onPick?: (complexNo: string) => void;
  height?: number;   // 급매찾기처럼 결과가 많은 화면에서 크게 쓸 때
  onLocate?: (lat: number, lng: number) => void;  // 내위치 이동 후 지역필터 전환 등(급매찾기)
}) {
  const [coords, setCoords] = useState<Coord[] | null>(null);
  const onLocateRef = useRef<typeof onLocate>(undefined);
  onLocateRef.current = onLocate;
  const elRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<any>(null);
  const ovsRef = useRef<any[]>([]);

  // 지도에 찍을 단지의 좌표만 골라 한 번에 받는다.
  const ids = useMemo(
    () => [...new Set(deals.map((d) => String(d.complex_no)).filter(Boolean))].slice(0, 60),
    [deals]);

  useEffect(() => {
    if (!API || ids.length === 0) { setCoords([]); return; }
    let dead = false;
    fetch(`${API}/complexes/coords?ids=${ids.join(",")}`)
      .then((r) => r.json())
      .then((j) => { if (!dead) setCoords(j.items || []); })
      .catch(() => { if (!dead) setCoords([]); });
    return () => { dead = true; };
  }, [ids.join(",")]); // eslint-disable-line

  useEffect(() => {
    if (!coords || coords.length === 0 || !elRef.current) return;
    let dead = false;
    // 같은 단지에 여러 평형 급매가 있으면 할인율이 가장 큰 것 하나만 핀으로 세운다.
    const best = new Map<string, DealPin>();
    for (const d of deals) {
      const k = String(d.complex_no);
      const prev = best.get(k);
      if (!prev || Math.abs(d.discount_min ?? 0) > Math.abs(prev.discount_min ?? 0)) best.set(k, d);
    }

    loadKakao().then(() => {
      if (dead || !elRef.current) return;
      const kakao = (window as any).kakao;
      const pts = coords
        .map((c) => ({ c, d: best.get(String(c.complex_no)) }))
        .filter((x) => x.d);
      if (pts.length === 0) return;

      if (!mapRef.current) {
        mapRef.current = new kakao.maps.Map(elRef.current, {
          center: new kakao.maps.LatLng(pts[0].c.lat, pts[0].c.lng),
          level: 6,
        });
        mapRef.current.setZoomable(false);   // 페이지 스크롤을 지도가 먹지 않게(랜딩이라 중요)
        attachMapControls(mapRef.current, elRef.current,
          { onLocate: (la, ln) => onLocateRef.current?.(la, ln) });   // 버튼 확대·축소는 스크롤 보호와 양립
      }
      const map = mapRef.current;
      ovsRef.current.forEach((o) => o.setMap(null));
      ovsRef.current = [];

      const bounds = new kakao.maps.LatLngBounds();
      for (const { c, d } of pts) {
        const pos = new kakao.maps.LatLng(c.lat, c.lng);
        bounds.extend(pos);
        const pct = d!.discount_min ? Math.round(Math.abs(d!.discount_min) * 100) : null;
        const el = document.createElement("div");
        el.className = "dmm-pin";
        el.innerHTML =
          `<b>${escapeHtml(d!.complex_name)}</b>` +
          `<span>${wonShort(d!.asking_min)}</span>` +
          (pct ? `<i>-${pct}%</i>` : "");
        el.addEventListener("click", () => onPick?.(String(c.complex_no)));
        const ov = new kakao.maps.CustomOverlay({
          position: pos, content: el, yAnchor: 1.12, clickable: true,
        });
        ov.setMap(map);
        ovsRef.current.push(ov);
      }
      map.setBounds(bounds, 26, 26, 26, 26);
    }).catch(() => { /* 지도 로드 실패는 조용히 — 아래 카드 목록은 그대로 보인다 */ });

    return () => { dead = true; };
  }, [coords, deals, onPick]);

  if (!API || ids.length === 0) return null;
  // 좌표를 못 받았으면 지도를 숨긴다(자리만 차지하는 빈 박스를 남기지 않는다).
  if (coords && coords.length === 0) return null;

  return (
    <div className="dmm">
      <div ref={elRef} className="dmm-map" aria-label="급매 단지 위치 지도"
        style={height ? { height } : undefined} />
      <div className="dmm-cap">핀을 누르면 아래 목록에서 해당 단지가 강조돼요</div>
    </div>
  );
}
