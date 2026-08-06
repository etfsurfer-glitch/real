// 사무소 매물 지도 — 매물장의 '지도보기'. 우리 사무소 네이버 연동매물 + 비공개매물을
// 한 화면에 찍고, 지도 위 오버레이 버튼으로 즉시 걸러 본다(목록으로 돌아갈 필요 없음).
// 좌표가 없는 매물(직접 등록 후 지오코딩 실패 등)은 지도에서만 빠지고 목록에는 남는다.
import { useEffect, useMemo, useRef, useState } from "react";
import { loadKakao, attachMapControls } from "../lib/kakaomap";
import { X, Lock, MapPin } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE;

type Item = {
  article_no: string; complex_name: string | null; building_name: string;
  trade_type: string; type: string; price_text: string; rent_price_text: string;
  address: string; area_name: string; floor_info: string;
  lat: number | null; lng: number | null;
  is_private?: boolean; visibility?: string; source_article_no?: string;
  manager?: string;
};

const TRADES = ["전체", "매매", "전세", "월세"];
const SOURCES = [["all", "전체"], ["naver", "네이버"], ["private", "비공개"]] as const;

const esc = (s: string) =>
  String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c] as string));

export default function OfficeMap({ authH, officeName, onClose }: {
  authH: () => Record<string, string>; officeName?: string | null; onClose: () => void;
}) {
  const [items, setItems] = useState<Item[] | null>(null);
  const [trade, setTrade] = useState("전체");
  const [src, setSrc] = useState<"all" | "naver" | "private">("all");
  const [cat, setCat] = useState("");
  const [err, setErr] = useState("");
  const mapEl = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<any>(null);
  const ovsRef = useRef<any[]>([]);

  // 지도에 다 찍어야 하므로 한 번에 넉넉히 받아둔다(필터는 클라이언트에서 즉시 반영).
  useEffect(() => {
    fetch(`${API_BASE}/lounge/listings?private=1&limit=3000`, { headers: authH() })
      .then((r) => r.json()).then((d) => setItems(d.listings || []))
      .catch(() => setErr("매물을 불러오지 못했어요"));
  }, [authH]);

  const cats = useMemo(() => {
    const s = new Set<string>();
    (items || []).forEach((i) => i.type && s.add(i.type));
    return [...s].sort();
  }, [items]);

  const shown = useMemo(() => (items || []).filter((i) => {
    if (trade !== "전체" && i.trade_type !== trade) return false;
    if (cat && i.type !== cat) return false;
    if (src === "naver" && i.is_private) return false;
    if (src === "private" && !i.is_private) return false;
    return true;
  }), [items, trade, cat, src]);

  const withXY = useMemo(() => shown.filter((i) => i.lat && i.lng), [shown]);

  // 지도 생성(한 번)
  useEffect(() => {
    let dead = false;
    loadKakao().then(() => {
      if (dead || !mapEl.current || mapRef.current) return;
      const kakao = (window as any).kakao;
      const map = new kakao.maps.Map(mapEl.current, {
        center: new kakao.maps.LatLng(37.4979, 127.0276), level: 6,
      });
      attachMapControls(map, mapEl.current);
      map.addControl(new kakao.maps.ZoomControl(), kakao.maps.ControlPosition.RIGHT);
      mapRef.current = map;
      setItems((v) => (v ? [...v] : v));   // 지도 준비 후 마커 그리기 트리거
    }).catch(() => setErr("지도를 불러오지 못했어요"));
    return () => { dead = true; };
  }, []);

  // 마커 갱신 + 첫 로드 시 전체가 보이도록 화면 맞춤
  useEffect(() => {
    const kakao = (window as any).kakao;
    const map = mapRef.current;
    if (!kakao?.maps || !map) return;
    ovsRef.current.forEach((o) => o.setMap(null));
    ovsRef.current = [];
    if (!withXY.length) return;
    const bounds = new kakao.maps.LatLngBounds();
    for (const it of withXY) {
      const pos = new kakao.maps.LatLng(it.lat, it.lng);
      bounds.extend(pos);
      const priv = !!it.is_private;
      const el = document.createElement("div");
      el.className = `om-pin${priv ? " om-priv" : ""}`;
      const price = it.trade_type === "월세" && it.rent_price_text
        ? `${esc(it.price_text)}/${esc(it.rent_price_text)}` : esc(it.price_text || "-");
      el.innerHTML =
        `<b>${price}</b>` +
        `<div class="om-tip"><div class="om-tip-t">${esc(it.complex_name || it.building_name || "매물")}` +
        `${priv ? ' <span class="om-tip-b">비공개</span>' : ""}</div>` +
        `<div class="om-tip-s">${esc(it.trade_type)} · ${esc(it.type)}` +
        `${it.area_name ? " · " + esc(it.area_name) : ""}${it.floor_info ? " · " + esc(it.floor_info) + "층" : ""}</div>` +
        `<div class="om-tip-a">${esc(it.address || "")}</div></div>`;
      const ov = new kakao.maps.CustomOverlay({ position: pos, content: el, yAnchor: 1.0, clickable: true, zIndex: 1 });
      el.addEventListener("mouseenter", () => ov.setZIndex(9999));
      el.addEventListener("mouseleave", () => ov.setZIndex(1));
      ov.setMap(map);
      ovsRef.current.push(ov);
    }
    map.setBounds(bounds, 40, 40, 40, 40);
  }, [withXY]);

  const noXY = shown.length - withXY.length;

  return (
    <div className="om-ov">
      <div className="om-head">
        <b><MapPin size={15} /> {officeName || "우리 사무소"} 매물 지도</b>
        <button onClick={onClose} aria-label="닫기"><X size={18} /></button>
      </div>
      <div className="om-map" ref={mapEl} />

      {/* 지도 위 오버레이 필터 */}
      <div className="om-ctl">
        <div className="om-row">
          {TRADES.map((t) => (
            <button key={t} className={trade === t ? "on" : ""} onClick={() => setTrade(t)}>{t}</button>
          ))}
        </div>
        <div className="om-row">
          {SOURCES.map(([k, l]) => (
            <button key={k} className={src === k ? "on" : ""} onClick={() => setSrc(k)}>
              {k === "private" && <Lock size={10} />}{l}
            </button>
          ))}
        </div>
        {cats.length > 1 && (
          <div className="om-row om-wrap">
            <button className={cat === "" ? "on" : ""} onClick={() => setCat("")}>전체유형</button>
            {cats.map((c) => (
              <button key={c} className={cat === c ? "on" : ""} onClick={() => setCat(c)}>{c}</button>
            ))}
          </div>
        )}
      </div>

      <div className="om-stat">
        {err ? err : items === null ? "불러오는 중…"
          : <>지도 <b>{withXY.length}</b>건{noXY > 0 && <span className="om-noxy"> · 좌표없음 {noXY}건</span>}</>}
      </div>
    </div>
  );
}
