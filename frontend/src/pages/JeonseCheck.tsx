import { useEffect, useRef, useState } from "react";
import { ShieldCheck, ShieldAlert, AlertTriangle, Search, MapPin } from "lucide-react";
import { loadKakao, geocodeRegion, wonShort } from "../lib/kakaomap";
import { useRegionFilter } from "../components/RegionSelect";

const API = import.meta.env.VITE_API_BASE;

type Verdict = { grade: string | null; ratio?: number; hug_limit: number; gongsi: number; gongsi_year: string; deposit: number | null; message: string };
type Nearby = { scope: string; sale_median: number | null; jeonse_median: number | null; risky_pct: number | null; n_buildings: number | null };
type Resp = { ok: boolean; error?: string; resolved?: { text: string; building: string | null; kind: string | null; matched_area: number | null }; verdict?: Verdict | null; nearby?: Nearby };
type Marker = { article_no: string; area_m2: number | null; deposit: number; lat: number; lng: number; floor: string | null; building: string };

function won(v: number | null | undefined): string {
  if (!v) return "-";
  if (v >= 1e8) { const e = Math.floor(v / 1e8); const m = Math.floor((v % 1e8) / 1e4); return m ? `${e}억 ${m.toLocaleString()}만` : `${e}억`; }
  return `${Math.floor(v / 1e4).toLocaleString()}만`;
}
const GRADE: Record<string, { c: string; icon: typeof ShieldCheck }> = {
  "안전": { c: "#0a9d57", icon: ShieldCheck }, "양호": { c: "#1f7ae0", icon: ShieldCheck },
  "주의": { c: "#e08a00", icon: AlertTriangle }, "위험": { c: "#d4332b", icon: ShieldAlert },
};

function Result({ res, sel }: { res: Resp; sel: Marker | null }) {
  const v = res.verdict, g = v?.grade ? GRADE[v.grade] : null;
  return (
    <div className="jc-result">
      {v && g && (
        <div className="jc-verdict" style={{ borderColor: g.c, background: `${g.c}0d` }}>
          <div className="jc-vhead" style={{ color: g.c }}>
            <g.icon size={26} /> <span className="jc-grade">{v.grade}</span>
            {v.ratio != null && <span className="jc-ratio">전세가율 {v.ratio}%</span>}
          </div>
          <div className="jc-vmsg">{v.message}</div>
          <div className="jc-bars">
            <div className="jc-bar-row"><span>전세 보증금</span><b>{won(v.deposit)}</b></div>
            <div className="jc-bar-row"><span>공시가격 ({v.gongsi_year})</span><b>{won(v.gongsi)}</b></div>
            <div className="jc-bar-row hug"><span>HUG 한도 (공시가×140%)</span><b>{won(v.hug_limit)}</b></div>
          </div>
          <div className="jc-gauge">
            <div className="jc-gauge-fill" style={{ width: `${Math.min((v.ratio || 0) / 1.6, 100)}%`, background: g.c }} />
            <span className="jc-gauge-100">100%</span><span className="jc-gauge-140">140%</span>
          </div>
        </div>
      )}
      {res.resolved && (
        <div className="jc-resolved">
          <b>{res.resolved.text}</b>
          <span>{res.resolved.kind}{res.resolved.matched_area ? ` · 전용 ${res.resolved.matched_area}㎡ 기준` : ""}{sel?.floor ? ` · ${sel.floor}층` : ""}</span>
        </div>
      )}
      {res.nearby && (
        <>
          <div className="ats-section" style={{ marginTop: 16 }}>{res.nearby.scope} 시세</div>
          <div className="jc-near">
            <div><span>매매 중위</span><b>{won(res.nearby.sale_median)}</b></div>
            <div><span>전세 중위</span><b>{won(res.nearby.jeonse_median)}</b></div>
            <div><span>위험 건물</span><b className={(res.nearby.risky_pct || 0) >= 30 ? "danger" : ""}>{res.nearby.risky_pct ?? "-"}%</b></div>
          </div>
        </>
      )}
      <p className="muted" style={{ fontSize: 11.5, marginTop: 14, lineHeight: 1.6 }}>
        ※ 공시가격 기준 <b>가격 위험도</b>입니다. <b>선순위 근저당·집주인 대출·세금 체납은 미반영</b> — 계약 전 <b>등기부등본</b>을 꼭 확인하세요. HUG 보증요건은 공시가격의 약 140%입니다.
      </p>
    </div>
  );
}

export default function JeonseCheck() {
  const { sidos, sigungus, dongs, sido, setSido, sigungu, setSigungu, dong, setDong } = useRegionFilter();
  const [mode, setMode] = useState<"map" | "manual">("map");
  const mapEl = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const overlays = useRef<any[]>([]);
  const loadRef = useRef<() => void>();
  const [status, setStatus] = useState("");
  const [sel, setSel] = useState<Marker | null>(null);
  const [res, setRes] = useState<Resp | null>(null);
  const [loading, setLoading] = useState(false);
  const [addr, setAddr] = useState(""); const [area, setArea] = useState(""); const [deposit, setDeposit] = useState("");

  const pick = (m: Marker) => {
    setSel(m); setLoading(true); setRes(null);
    fetch(`${API}/tools/jeonse-check?lat=${m.lat}&lng=${m.lng}&area=${m.area_m2 || 0}&deposit=${Math.round(m.deposit / 10000)}`)
      .then((r) => r.json()).then(setRes).catch(() => setRes({ ok: false, error: "조회 실패" })).finally(() => setLoading(false));
  };

  useEffect(() => {
    if (mode !== "map" || !API) return;
    let disposed = false; let debounce: ReturnType<typeof setTimeout>;
    loadKakao().then(() => {
      if (disposed || !mapEl.current) return;
      const kakao = window.kakao;
      const map = new kakao.maps.Map(mapEl.current, { center: new kakao.maps.LatLng(37.5665, 126.978), level: 5 });
      mapRef.current = map;
      map.addControl(new kakao.maps.ZoomControl(), kakao.maps.ControlPosition.RIGHT);
      const clear = () => { overlays.current.forEach((o) => o.setMap(null)); overlays.current = []; };
      const load = async () => {
        const b = map.getBounds(), sw = b.getSouthWest(), ne = b.getNorthEast();
        setStatus("불러오는 중…");
        try {
          const r = await fetch(`${API}/tools/jeonse-markers-bbox?swlat=${sw.getLat()}&swlng=${sw.getLng()}&nelat=${ne.getLat()}&nelng=${ne.getLng()}`);
          const j = await r.json();
          if (disposed) return; clear();
          if (j.too_wide) { setStatus("지도를 확대하면 전세 매물이 보여요"); return; }
          for (const m of (j.markers || []) as Marker[]) {
            const el = document.createElement("div");
            el.className = "jcm";
            el.innerHTML = `<b>${wonShort(m.deposit)}</b><i>${m.area_m2 || "-"}㎡</i>`;
            el.addEventListener("click", () => { pick(m); el.classList.add("on"); });
            const ov = new kakao.maps.CustomOverlay({ position: new kakao.maps.LatLng(m.lat, m.lng), content: el, yAnchor: 1.1, clickable: true, zIndex: 1 });
            el.addEventListener("mouseenter", () => ov.setZIndex(9999));
            el.addEventListener("mouseleave", () => ov.setZIndex(1));
            ov.setMap(map); overlays.current.push(ov);
          }
          setStatus(`${(j.markers || []).length}개 전세 매물${j.too_many ? " (확대하면 더 정확)" : ""}`);
        } catch { setStatus("불러오기 실패"); }
      };
      loadRef.current = load;
      kakao.maps.event.addListener(map, "idle", () => { clearTimeout(debounce); debounce = setTimeout(load, 250); });
      load();
    }).catch(() => setStatus("지도 로드 실패 — 잠시 후 다시"));
    return () => { disposed = true; clearTimeout(debounce); overlays.current.forEach((o) => o.setMap(null)); overlays.current = []; };
  }, [mode]);

  // 지역 드롭다운 선택 → 지도 이동
  useEffect(() => {
    if (mode !== "map" || !mapRef.current) return;
    const nm = [sidos.find((s) => s.code === sido)?.name, sigungus.find((s) => s.code === sigungu)?.name, dongs.find((d) => d.code === dong)?.name].filter(Boolean).join(" ");
    if (!nm) return;
    geocodeRegion(nm).then((c) => { if (c && mapRef.current) { mapRef.current.setLevel(dong ? 4 : sigungu ? 5 : 7); mapRef.current.panTo(new window.kakao.maps.LatLng(c.lat, c.lng)); } });
  }, [sido, sigungu, dong, mode]);

  const checkManual = () => {
    if (!addr.trim()) return; setLoading(true); setRes(null); setSel(null);
    fetch(`${API}/tools/jeonse-check?addr=${encodeURIComponent(addr.trim())}&area=${area || 0}&deposit=${deposit || 0}`)
      .then((r) => r.json()).then(setRes).catch(() => setRes({ ok: false, error: "조회 실패" })).finally(() => setLoading(false));
  };

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: "6px 4px 40px" }}>
      <h2 style={{ fontSize: 21, fontWeight: 800, color: "#13294b", margin: "0 0 4px" }}>전세 안전 감별기</h2>
      <p className="muted" style={{ fontSize: 13, margin: "0 0 12px" }}>
        지도에서 <b>전세 매물을 누르면</b> <b>공시가격(HUG 기준)</b>으로 깡통전세 위험을 알려드려요.
      </p>

      <div className="jc-seg">
        <button className={mode === "map" ? "on" : ""} onClick={() => { setMode("map"); setRes(null); setSel(null); }}>지도에서 찾기</button>
        <button className={mode === "manual" ? "on" : ""} onClick={() => { setMode("manual"); setRes(null); setSel(null); }}>주소 직접 입력</button>
      </div>

      {mode === "map" ? (
        <>
          <div className="dong-pick" style={{ marginTop: 12 }}>
            <select value={sido} onChange={(e) => setSido(e.target.value)}><option value="">시·도</option>{sidos.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}</select>
            <select value={sigungu} onChange={(e) => setSigungu(e.target.value)} disabled={!sido}><option value="">시·군·구</option>{sigungus.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}</select>
            <select value={dong} onChange={(e) => setDong(e.target.value)} disabled={!sigungu}><option value="">읍·면·동</option>{dongs.map((d) => <option key={d.code} value={d.code}>{d.name}</option>)}</select>
          </div>
          <div className="jc-map-wrap">
            <div ref={mapEl} className="jc-map" />
            <div className="jc-map-status"><MapPin size={12} /> {status || "지도를 움직여 매물을 찾아보세요"}</div>
          </div>
        </>
      ) : (
        <div className="jc-form" style={{ marginTop: 12 }}>
          <label>주소 <span>지번 (예: 서울 강서구 화곡동 102-119)</span>
            <input value={addr} onChange={(e) => setAddr(e.target.value)} onKeyDown={(e) => e.key === "Enter" && checkManual()} placeholder="서울 강서구 화곡동 102-119" /></label>
          <div className="jc-row">
            <label>전용면적 (㎡)<input type="number" value={area} onChange={(e) => setArea(e.target.value)} placeholder="35" /></label>
            <label>보증금 (만원) {deposit && <span>{won(Number(deposit) * 10000)}</span>}<input type="number" value={deposit} onChange={(e) => setDeposit(e.target.value)} onKeyDown={(e) => e.key === "Enter" && checkManual()} placeholder="26000" /></label>
          </div>
          <button className="jc-go" onClick={checkManual} disabled={loading || !addr.trim()}><Search size={16} /> {loading ? "조회 중…" : "감별하기"}</button>
        </div>
      )}

      {loading && <div className="jc-hint" style={{ textAlign: "center" }}>공시가격 조회 중…</div>}
      {res && !res.ok && <div className="jc-err">{res.error}</div>}
      {res?.ok && <Result res={res} sel={sel} />}
    </div>
  );
}
