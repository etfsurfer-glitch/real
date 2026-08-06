import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { School, X } from "lucide-react";
import { loadKakao, escapeHtml, attachMapControls } from "../lib/kakaomap";

const API = import.meta.env.VITE_API_BASE;

// 배정 초등학교 팝업 — 카카오지도에 학구도(통학구역) 경계 + 아파트 + 배정교 +
// 인근 초등학교를 표시. 지하철 주변역 팝업(SubwayModal)과 같은 사용 흐름.
type Sch = { school_id: string; name: string; lat: number; lng: number; distance_m: number; walk_min: number };
type Res = {
  complex_name: string; lat: number; lng: number; src: string | null;
  assigned: Sch[]; zones: number[][][][] | number[][][]; nearby: Sch[];
};

const shortName = (n: string) => n.replace("등학교", "");

export default function SchoolModal({ complexNo, onClose }: { complexNo: string; onClose: () => void }) {
  const [data, setData] = useState<Res | null>(null);
  const [err, setErr] = useState("");
  const mapEl = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);

  useEffect(() => {
    fetch(`${API}/complex/${complexNo}/school-map`)
      .then((r) => { if (!r.ok) throw new Error(r.status === 404 ? "단지 좌표가 없어요" : `오류 ${r.status}`); return r.json(); })
      .then(setData)
      .catch((e) => setErr(e instanceof Error ? e.message : "불러오기 실패"));
  }, [complexNo]);

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

      // 학구도 경계 — 배정의 근거가 되는 통학구역을 옅게 칠해준다
      for (const zone of data.zones as number[][][][]) {
        for (const ring of zone) {
          const path = ring.map(([lo, la]) => new kakao.maps.LatLng(la, lo));
          new kakao.maps.Polygon({
            map, path,
            strokeWeight: 2, strokeColor: "#0d7a56", strokeOpacity: 0.9, strokeStyle: "shortdash",
            fillColor: "#0d7a56", fillOpacity: 0.08,
          });
          path.forEach((p: any) => bounds.extend(p));
        }
      }

      const aptPos = new kakao.maps.LatLng(data.lat, data.lng);
      bounds.extend(aptPos);
      new kakao.maps.CustomOverlay({
        map, position: aptPos, yAnchor: 1.1,
        content: `<div class="swm-apt">🏠 ${escapeHtml(data.complex_name)}</div>`,
      });
      for (const sc of data.assigned) {
        const pos = new kakao.maps.LatLng(sc.lat, sc.lng);
        bounds.extend(pos);
        new kakao.maps.CustomOverlay({
          map, position: pos, yAnchor: 0.5,
          content: `<div class="scm-assigned">🏫 ${escapeHtml(shortName(sc.name))}<em>${sc.walk_min}분</em></div>`,
        });
      }
      for (const sc of data.nearby) {
        new kakao.maps.CustomOverlay({
          map, position: new kakao.maps.LatLng(sc.lat, sc.lng), yAnchor: 0.5,
          content: `<div class="scm-near">${escapeHtml(shortName(sc.name))}</div>`,
        });
      }
      map.setBounds(bounds, 28, 28, 28, 28);
    }).catch(() => setErr("지도 로드 실패 — 목록으로 확인해주세요"));
    return () => { cancelled = true; };
  }, [data]);

  const focus = (sc: Sch) => {
    const kakao = window.kakao;
    if (mapRef.current && kakao?.maps) mapRef.current.panTo(new kakao.maps.LatLng(sc.lat, sc.lng));
  };

  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card swm-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <span className="modal-title">
            <School size={15} strokeWidth={2.2} aria-hidden /> {data ? `${data.complex_name} 배정 초등학교` : "배정 초등학교"}
          </span>
          <button className="phone-banner-x" aria-label="닫기" onClick={onClose}><X size={16} /></button>
        </div>

        {err && <div className="modal-msg">{err}</div>}
        {!data && !err && <div className="muted" style={{ padding: "16px 4px", fontSize: 13 }}>학구 정보를 찾는 중…</div>}

        {data && (
          <>
            <div ref={mapEl} className="swm-map" />
            <div className="swm-list">
              {data.assigned.map((sc) => (
                <button key={sc.school_id} type="button" className="swm-row" onClick={() => focus(sc)}>
                  <span className="scm-badge">{data.src === "near" ? "인근" : "배정"}</span>
                  <span className="swm-name">{sc.name}</span>
                  <span className="swm-lines" />
                  <span className="swm-dist">{sc.distance_m >= 1000 ? `${(sc.distance_m / 1000).toFixed(1)}km` : `${sc.distance_m}m`} · 도보 {sc.walk_min}분</span>
                </button>
              ))}
              {data.nearby.map((sc) => (
                <button key={sc.school_id} type="button" className="swm-row" onClick={() => focus(sc)}>
                  <span className="scm-badge off">참고</span>
                  <span className="swm-name" style={{ fontWeight: 600, color: "#66748a" }}>{sc.name}</span>
                  <span className="swm-lines" />
                  <span className="swm-dist">{sc.distance_m >= 1000 ? `${(sc.distance_m / 1000).toFixed(1)}km` : `${sc.distance_m}m`} · 도보 {sc.walk_min}분</span>
                </button>
              ))}
            </div>
            <p className="muted" style={{ fontSize: 11, margin: "8px 0 0" }}>
              {data.src === "near"
                ? "학구도 데이터에 포함되지 않은 지역이라 인근 학교를 보여드려요 (배정 아님)"
                : "초록 점선 = 학구도(통학구역) 경계 · 배정은 교육청 고시 기준이며 실제 배정은 변동될 수 있어요"}
              {" · "}거리는 직선 기준(도보 = 직선 ×1.25 ÷ 80m/분)
            </p>
          </>
        )}
      </div>
    </div>,
    document.body,
  );
}
