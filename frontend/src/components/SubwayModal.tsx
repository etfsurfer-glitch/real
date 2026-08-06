import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { TrainFront, X } from "lucide-react";
import { loadKakao, escapeHtml, attachMapControls } from "../lib/kakaomap";

const API = import.meta.env.VITE_API_BASE;

// 주변 지하철역 팝업 — 카카오지도에 아파트+반경 2km 역을 찍고, 거리순 목록 제공.
// 지하철 표시가 있는 곳(관심단지 카드·단지 종합) 어디서든 연다.
type Station = {
  station: string; lines: string; lat: number; lng: number;
  distance_m: number; walk_min: number;
};
type Res = {
  complex_name: string; lat: number; lng: number; radius_km: number; items: Station[];
};

export default function SubwayModal({ complexNo, onClose }: { complexNo: string; onClose: () => void }) {
  const [data, setData] = useState<Res | null>(null);
  const [err, setErr] = useState("");
  const mapEl = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);

  useEffect(() => {
    fetch(`${API}/complex/${complexNo}/subway-nearby?radius_km=2&limit=8`)
      .then((r) => { if (!r.ok) throw new Error(r.status === 404 ? "단지 좌표가 없어요" : `오류 ${r.status}`); return r.json(); })
      .then(setData)
      .catch((e) => setErr(e instanceof Error ? e.message : "불러오기 실패"));
  }, [complexNo]);

  // 지도 렌더 — 데이터 도착 후 SDK 로드해 아파트·역 오버레이 + 범위 맞춤
  useEffect(() => {
    if (!data || !mapEl.current) return;
    let cancelled = false;
    loadKakao().then(() => {
      if (cancelled || !mapEl.current) return;
      const kakao = window.kakao;
      const map = new kakao.maps.Map(mapEl.current, {
        center: new kakao.maps.LatLng(data.lat, data.lng), level: 5,
      });
      attachMapControls(map, mapEl.current, { locate: false });
      mapRef.current = map;
      const bounds = new kakao.maps.LatLngBounds();

      const aptPos = new kakao.maps.LatLng(data.lat, data.lng);
      bounds.extend(aptPos);
      new kakao.maps.CustomOverlay({
        map, position: aptPos, yAnchor: 1.1,
        content: `<div class="swm-apt">🏠 ${escapeHtml(data.complex_name)}</div>`,
      });

      for (const st of data.items) {
        const pos = new kakao.maps.LatLng(st.lat, st.lng);
        bounds.extend(pos);
        new kakao.maps.CustomOverlay({
          map, position: pos, yAnchor: 0.5,
          content: `<div class="swm-st" title="${escapeHtml(st.lines)}">🚇 ${escapeHtml(st.station)}<em>${st.walk_min}분</em></div>`,
        });
      }
      if (data.items.length > 0) map.setBounds(bounds, 24, 24, 24, 24);
    }).catch(() => setErr("지도 로드 실패 — 목록으로 확인해주세요"));
    return () => { cancelled = true; };
  }, [data]);

  const focus = (st: Station) => {
    const kakao = window.kakao;
    if (mapRef.current && kakao?.maps) {
      mapRef.current.panTo(new kakao.maps.LatLng(st.lat, st.lng));
    }
  };

  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card swm-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <span className="modal-title">
            <TrainFront size={15} strokeWidth={2.2} aria-hidden /> {data ? `${data.complex_name} 주변역` : "주변역"}
          </span>
          <button className="phone-banner-x" aria-label="닫기" onClick={onClose}><X size={16} /></button>
        </div>

        {err && <div className="modal-msg">{err}</div>}
        {!data && !err && <div className="muted" style={{ padding: "16px 4px", fontSize: 13 }}>주변 역을 찾는 중…</div>}

        {data && (
          <>
            <div ref={mapEl} className="swm-map" />
            {data.items.length === 0 ? (
              <div className="muted" style={{ padding: "12px 4px", fontSize: 13 }}>반경 {data.radius_km}km 안에 지하철역이 없어요.</div>
            ) : (
              <div className="swm-list">
                {data.items.map((st, i) => (
                  <button key={st.station} type="button" className="swm-row" onClick={() => focus(st)}>
                    <span className="swm-rank">{i + 1}</span>
                    <span className="swm-name">{st.station}</span>
                    <span className="swm-lines">{st.lines}</span>
                    <span className="swm-dist">{st.distance_m >= 1000 ? `${(st.distance_m / 1000).toFixed(1)}km` : `${st.distance_m}m`} · 도보 {st.walk_min}분</span>
                  </button>
                ))}
              </div>
            )}
            <p className="muted" style={{ fontSize: 11, margin: "8px 0 0" }}>
              직선거리 기준(도보 = 직선 ×1.25 ÷ 80m/분) · 역을 누르면 지도가 이동해요
            </p>
          </>
        )}
      </div>
    </div>,
    document.body,
  );
}
