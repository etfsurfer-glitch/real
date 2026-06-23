import { useEffect, useRef, useState } from "react";
import { ShieldCheck, ShieldAlert, AlertTriangle, Search, MapPin, Home } from "lucide-react";
import { loadKakao, geocodeRegion } from "../lib/kakaomap";
import { useRegionFilter } from "../components/RegionSelect";

const API = import.meta.env.VITE_API_BASE;

type Unit = { area_m2: number; gongsi: number; hug_limit: number; n: number };
type Nearby = { scope: string; sale_median: number | null; jeonse_median: number | null; risky_pct: number | null; n_buildings: number | null };
type Verdict = { grade: string | null; ratio?: number; hug_limit: number; gongsi: number; gongsi_year: string; deposit: number | null; message: string };
type Resp = { ok: boolean; error?: string; resolved?: { text: string; building: string | null; kind: string | null }; units?: Unit[]; verdict?: Verdict | null; nearby?: Nearby };
type Bld = { key: string; name: string; umd: string; jibun: string; area_m2: number | null; tx_count: number; lat: number; lng: number };

function won(v: number | null | undefined): string {
  if (!v) return "-";
  if (v >= 1e8) { const e = Math.floor(v / 1e8); const m = Math.floor((v % 1e8) / 1e4); return m ? `${e}억 ${m.toLocaleString()}만` : `${e}억`; }
  return `${Math.floor(v / 1e4).toLocaleString()}만`;
}
const GRADE: Record<string, { c: string; icon: typeof ShieldCheck }> = {
  "안전": { c: "#0a9d57", icon: ShieldCheck }, "양호": { c: "#1f7ae0", icon: ShieldCheck },
  "주의": { c: "#e08a00", icon: AlertTriangle }, "위험": { c: "#d4332b", icon: ShieldAlert },
};
// 클라이언트 판정 (HUG 기준 = 공시가격 ×140%)
function judge(depositWon: number, gongsi: number) {
  const r = depositWon / gongsi;
  if (r <= 1.0) return { grade: "안전", msg: "공시가격 이하입니다." };
  if (r <= 1.2) return { grade: "양호", msg: "공시가격을 넘지만 HUG 한도 안입니다." };
  if (r <= 1.4) return { grade: "주의", msg: "HUG 보증한도(공시가격 140%)에 근접합니다." };
  return { grade: "위험", msg: "공시가격 140% 초과 — HUG 전세보증도 거부되는 깡통전세 위험 수준입니다." };
}

export default function JeonseCheck() {
  const { sidos, sigungus, dongs, sido, setSido, sigungu, setSigungu, dong, setDong } = useRegionFilter();
  const [mode, setMode] = useState<"map" | "manual">("map");
  const mapEl = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const overlays = useRef<any[]>([]);
  const [status, setStatus] = useState("");
  const [sel, setSel] = useState<Bld | null>(null);
  const [res, setRes] = useState<Resp | null>(null);
  const [loading, setLoading] = useState(false);
  const [unit, setUnit] = useState<Unit | null>(null);   // 선택한 면적
  const [dep, setDep] = useState("");                     // 전세 보증금(만원)
  const [addr, setAddr] = useState(""); const [mArea, setMArea] = useState(""); const [mDep, setMDep] = useState("");

  const check = (b: Bld) => {
    setLoading(true); setUnit(null); setDep("");
    fetch(`${API}/tools/jeonse-check?lat=${b.lat}&lng=${b.lng}`).then((r) => r.json()).then((d) => {
      setRes(d);
      if (d.units?.length === 1) setUnit(d.units[0]);   // 면적 1개면 자동 선택
    }).catch(() => setRes({ ok: false, error: "조회 실패" })).finally(() => setLoading(false));
  };
  const pickBld = (b: Bld) => { setSel(b); setRes(null); check(b); };

  useEffect(() => {
    if (mode !== "map" || !API) return;
    let disposed = false; let debounce: ReturnType<typeof setTimeout>;
    loadKakao().then(() => {
      if (disposed || !mapEl.current) return;
      const kakao = window.kakao;
      const map = new kakao.maps.Map(mapEl.current, { center: new kakao.maps.LatLng(37.5412, 126.8407), level: 4 });
      mapRef.current = map;
      map.addControl(new kakao.maps.ZoomControl(), kakao.maps.ControlPosition.RIGHT);
      const clear = () => { overlays.current.forEach((o) => o.setMap(null)); overlays.current = []; };
      const load = async () => {
        const b = map.getBounds(), sw = b.getSouthWest(), ne = b.getNorthEast();
        setStatus("불러오는 중…");
        try {
          const r = await fetch(`${API}/tools/villa-bbox?swlat=${sw.getLat()}&swlng=${sw.getLng()}&nelat=${ne.getLat()}&nelng=${ne.getLng()}`);
          const j = await r.json();
          if (disposed) return; clear();
          if (j.too_wide) { setStatus("지도를 확대하면 빌라가 보여요"); return; }
          for (const bld of (j.buildings || []) as Bld[]) {
            const el = document.createElement("div");
            el.className = "jvm"; el.title = bld.name;
            el.addEventListener("click", () => { pickBld(bld); document.querySelectorAll(".jvm.on").forEach((e) => e.classList.remove("on")); el.classList.add("on"); });
            const ov = new kakao.maps.CustomOverlay({ position: new kakao.maps.LatLng(bld.lat, bld.lng), content: el, yAnchor: 0.5, xAnchor: 0.5, clickable: true, zIndex: 1 });
            ov.setMap(map); overlays.current.push(ov);
          }
          setStatus(`평가 가능한 빌라 ${(j.buildings || []).length}곳${j.too_many ? "+ (확대하면 더 정확)" : ""} — 핀을 누르세요`);
        } catch { setStatus("불러오기 실패"); }
      };
      kakao.maps.event.addListener(map, "idle", () => { clearTimeout(debounce); debounce = setTimeout(load, 250); });
      load();
    }).catch(() => setStatus("지도 로드 실패"));
    return () => { disposed = true; clearTimeout(debounce); overlays.current.forEach((o) => o.setMap(null)); overlays.current = []; };
  }, [mode]);

  useEffect(() => {
    if (mode !== "map" || !mapRef.current) return;
    const nm = [sidos.find((s) => s.code === sido)?.name, sigungus.find((s) => s.code === sigungu)?.name, dongs.find((d) => d.code === dong)?.name].filter(Boolean).join(" ");
    if (!nm) return;
    geocodeRegion(nm).then((c) => { if (c && mapRef.current) { mapRef.current.setLevel(dong ? 4 : sigungu ? 5 : 7); mapRef.current.panTo(new window.kakao.maps.LatLng(c.lat, c.lng)); } });
  }, [sido, sigungu, dong, mode]);

  const checkManual = () => {
    if (!addr.trim()) return; setLoading(true); setRes(null); setSel(null); setUnit(null);
    fetch(`${API}/tools/jeonse-check?addr=${encodeURIComponent(addr.trim())}&area=${mArea || 0}&deposit=${mDep || 0}`)
      .then((r) => r.json()).then(setRes).catch(() => setRes({ ok: false, error: "조회 실패" })).finally(() => setLoading(false));
  };

  // 지도 빌라: 선택 면적+보증금으로 클라이언트 판정 / 단독 등: 서버 verdict
  const depWon = dep ? Number(dep) * 10000 : 0;
  const liveV = unit && depWon ? { ...judge(depWon, unit.gongsi), gongsi: unit.gongsi, hug: unit.hug_limit, ratio: Math.round(depWon / unit.gongsi * 100) } : null;
  const srvV = res?.verdict;

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: "6px 4px 40px" }}>
      <h2 style={{ fontSize: 21, fontWeight: 800, color: "#13294b", margin: "0 0 4px" }}>전세 안전 감별기</h2>
      <p className="muted" style={{ fontSize: 13, margin: "0 0 12px" }}>
        지도에서 <b>빌라를 누르고 → 면적을 고르고 → 전세 보증금</b>을 넣으면 <b>공시가격(HUG 기준)</b>으로 깡통전세 위험을 알려드려요.
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
          <div className="jc-map-wrap"><div ref={mapEl} className="jc-map" /><div className="jc-map-status"><MapPin size={12} /> {status || "지도를 움직여 빌라를 찾아보세요"}</div></div>
        </>
      ) : (
        <div className="jc-form" style={{ marginTop: 12 }}>
          <label>주소 <span>지번 (예: 서울 강서구 화곡동 102-119)</span>
            <input value={addr} onChange={(e) => setAddr(e.target.value)} onKeyDown={(e) => e.key === "Enter" && checkManual()} placeholder="서울 강서구 화곡동 102-119" /></label>
          <div className="jc-row">
            <label>전용면적 (㎡)<input type="number" value={mArea} onChange={(e) => setMArea(e.target.value)} placeholder="35" /></label>
            <label>보증금 (만원) {mDep && <span>{won(Number(mDep) * 10000)}</span>}<input type="number" value={mDep} onChange={(e) => setMDep(e.target.value)} onKeyDown={(e) => e.key === "Enter" && checkManual()} placeholder="26000" /></label>
          </div>
          <button className="jc-go" onClick={checkManual} disabled={loading || !addr.trim()}><Search size={16} /> {loading ? "조회 중…" : "감별하기"}</button>
        </div>
      )}

      {sel && mode === "map" && <div className="jc-sel"><Home size={14} /> <b>{res?.resolved?.building || sel.name}</b> <span>실거래 {sel.tx_count}건</span></div>}
      {loading && <div className="jc-hint" style={{ textAlign: "center" }}>공시가격 조회 중…</div>}
      {res && !res.ok && <div className="jc-err">{res.error}</div>}

      {res?.ok && (
        <div className="jc-result">
          {/* 공동주택: 면적 선택 → 보증금 → 판정 */}
          {res.units && res.units.length > 0 ? (
            <>
              <div className="ats-section" style={{ marginTop: 14 }}>면적(전용)을 고르세요 — 면적마다 공시가격이 달라요</div>
              <div className="jc-units">
                {res.units.map((u) => (
                  <button key={u.area_m2} className={`jc-unit ${unit?.area_m2 === u.area_m2 ? "on" : ""}`} onClick={() => setUnit(u)}>
                    <b>{u.area_m2}㎡</b><span>공시 {won(u.gongsi)}</span>
                  </button>
                ))}
              </div>
              {unit && (
                <div className="jc-gongsi">
                  <div className="jc-gongsi-row"><span>공시가격 (전용 {unit.area_m2}㎡)</span><b>{won(unit.gongsi)}</b></div>
                  <div className="jc-gongsi-row hug"><span>HUG 한도 (공시가×140%)</span><b>{won(unit.hug_limit)}</b></div>
                  <div className="jc-depbox">
                    <input type="number" value={dep} onChange={(e) => setDep(e.target.value)} placeholder="전세 보증금 (만원)" />
                    {dep && <span className="jc-dep-eok">{won(depWon)}</span>}
                  </div>
                </div>
              )}
              {liveV && (
                <div className="jc-verdict" style={{ borderColor: GRADE[liveV.grade].c, background: `${GRADE[liveV.grade].c}0d`, marginTop: 12 }}>
                  <div className="jc-vhead" style={{ color: GRADE[liveV.grade].c }}>
                    {(() => { const I = GRADE[liveV.grade].icon; return <I size={26} />; })()}
                    <span className="jc-grade">{liveV.grade}</span><span className="jc-ratio">전세가율 {liveV.ratio}%</span>
                  </div>
                  <div className="jc-vmsg">{liveV.msg}</div>
                  <div className="jc-gauge"><div className="jc-gauge-fill" style={{ width: `${Math.min(liveV.ratio / 1.6, 100)}%`, background: GRADE[liveV.grade].c }} /><span className="jc-gauge-100">100%</span><span className="jc-gauge-140">140%</span></div>
                </div>
              )}
            </>
          ) : srvV ? (
            <div className="jc-gongsi">
              <div className="jc-gongsi-row"><span>공시가격 ({srvV.gongsi_year}) · {res.resolved?.kind}</span><b>{won(srvV.gongsi)}</b></div>
              <div className="jc-gongsi-row hug"><span>HUG 한도 (공시가×140%)</span><b>{won(srvV.hug_limit)}</b></div>
              {srvV.grade && <div className="jc-vmsg" style={{ marginTop: 8, color: GRADE[srvV.grade]?.c, fontWeight: 700 }}>{srvV.grade} — 전세가율 {srvV.ratio}% · {srvV.message}</div>}
            </div>
          ) : null}

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
      )}
    </div>
  );
}
