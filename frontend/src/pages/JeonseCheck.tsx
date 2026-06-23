import { useEffect, useRef, useState } from "react";
import { ShieldCheck, ShieldAlert, AlertTriangle, Search, Home, X, ExternalLink } from "lucide-react";
import { loadKakao, geocodeRegion } from "../lib/kakaomap";
import { useRegionFilter } from "../components/RegionSelect";
import { openListingPopup } from "../lib/listingPopup";

const API = import.meta.env.VITE_API_BASE;

type Unit = { area_m2: number | null; gongsi: number; hug_limit: number; n: number; whole?: boolean };
type Nearby = { scope: string; sale_median: number | null; jeonse_median: number | null; risky_pct: number | null; n_buildings: number | null };
type Verdict = { grade: string | null; ratio?: number; hug_limit: number; gongsi: number; gongsi_year: string; message: string };
type Sale = { date: string; amount: number; area_m2: number | null; floor: number | null };
type Rent = { date: string; deposit: number; monthly: number; area_m2: number | null; floor: number | null };
type Listing = { article_no: string; trade: string; area_m2: number | null; price: number; rent: number; floor: string | null; dup?: number; ratio?: number; grade?: string; naver_url: string };
type Resp = { ok: boolean; error?: string; resolved?: { text: string; building: string | null; kind: string | null }; units?: Unit[]; verdict?: Verdict | null; nearby?: Nearby; building_deals?: { sales: Sale[]; rents: Rent[] }; building_listings?: Listing[] };
type Bld = { name: string; tx_count?: number; lat: number; lng: number };

function won(v: number | null | undefined): string {
  if (!v) return "-";
  if (v >= 1e8) { const e = Math.floor(v / 1e8); const m = Math.floor((v % 1e8) / 1e4); return m ? `${e}억 ${m.toLocaleString()}만` : `${e}억`; }
  return `${Math.floor(v / 1e4).toLocaleString()}만`;
}
const GRADE: Record<string, { c: string; icon: typeof ShieldCheck }> = {
  "양호": { c: "#1f9d63", icon: ShieldCheck },
  "보증한도 확인": { c: "#d4a017", icon: AlertTriangle },
  "HUG 초과 가능": { c: "#e0701e", icon: AlertTriangle },
  "고위험": { c: "#d23b3b", icon: ShieldAlert },
};
// HUG 보증한도 = 공시가격 × 140%(주택가격 환산) × 90%(담보인정) = 공시가격 × 126%
function judge(depositWon: number, gongsi: number) {
  const r = depositWon / gongsi;
  if (r <= 1.15) return { grade: "양호", msg: "공시가격 기준으로도 여유가 있어요." };
  if (r <= 1.26) return { grade: "보증한도 확인", msg: "HUG 보증한도(공시가×126%)에 임박했어요. 선순위채권·근저당을 꼭 확인하세요." };
  if (r <= 1.40) return { grade: "HUG 초과 가능", msg: "공시가격 기준 HUG 보증한도를 넘을 수 있어요. KB시세·감정가 등 대체 기준 확인이 필요해요." };
  return { grade: "고위험", msg: "공시가 환산 주택가격(140%)을 넘는 수준 — 깡통·보증거절 가능성이 큽니다." };
}

export default function JeonseCheck() {
  const { sidos, sigungus, dongs, sido, setSido, sigungu, setSigungu, dong, setDong } = useRegionFilter();
  const mapEl = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const overlays = useRef<any[]>([]);
  const pinRef = useRef<any>(null);   // 주소검색 임시 핀
  const [status, setStatus] = useState("");
  const [sel, setSel] = useState<Bld | null>(null);
  const [res, setRes] = useState<Resp | null>(null);
  const [loading, setLoading] = useState(false);
  const [unit, setUnit] = useState<Unit | null>(null);
  const [dep, setDep] = useState("");
  const [lien, setLien] = useState("");   // 선순위 채권(근저당·대출), 만원
  const [addr, setAddr] = useState("");

  const checkCoord = (b: Bld) => {
    setSel(b); setRes(null); setUnit(null); setDep(""); setLien(""); setLoading(true);
    fetch(`${API}/tools/jeonse-check?lat=${b.lat}&lng=${b.lng}`).then((r) => r.json()).then((d) => {
      setRes(d);
      if (d.units?.length === 1) setUnit(d.units[0]);
    }).catch(() => setRes({ ok: false, error: "조회 실패" })).finally(() => setLoading(false));
  };

  const searchAddr = () => {
    if (!addr.trim()) return;
    geocodeRegion(addr.trim()).then((c) => {
      if (!c || !mapRef.current) { setStatus("주소를 찾지 못했어요"); return; }
      const kakao = window.kakao;
      mapRef.current.setLevel(3);
      mapRef.current.panTo(new kakao.maps.LatLng(c.lat, c.lng));
      if (pinRef.current) pinRef.current.setMap(null);
      const el = document.createElement("div"); el.className = "jvm on";
      pinRef.current = new kakao.maps.CustomOverlay({ position: new kakao.maps.LatLng(c.lat, c.lng), content: el, yAnchor: 0.5, xAnchor: 0.5, zIndex: 5 });
      pinRef.current.setMap(mapRef.current);
      checkCoord({ name: addr.trim(), lat: c.lat, lng: c.lng });
    });
  };

  useEffect(() => {
    if (!API) return;
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
          for (const bld of (j.buildings || []) as { name: string; tx_count: number; lat: number; lng: number }[]) {
            const el = document.createElement("div");
            el.className = "jvm"; el.title = bld.name;
            el.addEventListener("click", () => {
              if (pinRef.current) { pinRef.current.setMap(null); pinRef.current = null; }
              document.querySelectorAll(".jvm.on").forEach((e) => e.classList.remove("on")); el.classList.add("on");
              checkCoord({ name: bld.name, tx_count: bld.tx_count, lat: bld.lat, lng: bld.lng });
            });
            const ov = new kakao.maps.CustomOverlay({ position: new kakao.maps.LatLng(bld.lat, bld.lng), content: el, yAnchor: 0.5, xAnchor: 0.5, clickable: true, zIndex: 1 });
            ov.setMap(map); overlays.current.push(ov);
          }
          setStatus(`빌라 ${(j.buildings || []).length}곳${j.too_many ? "+" : ""} · 핀을 누르거나 주소를 검색하세요`);
        } catch { setStatus("불러오기 실패"); }
      };
      kakao.maps.event.addListener(map, "idle", () => { clearTimeout(debounce); debounce = setTimeout(load, 250); });
      load();
    }).catch(() => setStatus("지도 로드 실패"));
    return () => { disposed = true; clearTimeout(debounce); overlays.current.forEach((o) => o.setMap(null)); };
  }, []);

  useEffect(() => {
    if (!mapRef.current) return;
    const nm = [sidos.find((s) => s.code === sido)?.name, sigungus.find((s) => s.code === sigungu)?.name, dongs.find((d) => d.code === dong)?.name].filter(Boolean).join(" ");
    if (!nm) return;
    geocodeRegion(nm).then((c) => { if (c && mapRef.current) { mapRef.current.setLevel(dong ? 4 : sigungu ? 5 : 7); mapRef.current.panTo(new window.kakao.maps.LatLng(c.lat, c.lng)); } });
  }, [sido, sigungu, dong]);

  const depWon = dep ? Number(dep) * 10000 : 0;
  const lienWon = lien ? Number(lien) * 10000 : 0;
  const totalWon = depWon + lienWon;   // 전세보증금 + 선순위 채권
  const v = unit && depWon ? { ...judge(totalWon, unit.gongsi), ratio: Math.round(totalWon / unit.gongsi * 100) } : null;
  const srvV = res?.verdict;

  return (
    <div style={{ maxWidth: 1040, margin: "0 auto", padding: "6px 4px 40px" }}>
      <h2 style={{ fontSize: 22, fontWeight: 800, color: "#13294b", margin: "0 0 3px" }}>깡통전세지수</h2>
      <p className="muted" style={{ fontSize: 13, margin: "0 0 10px" }}>
        빌라를 누르거나 주소를 검색 → 면적 선택 → 전세 보증금 입력 → <b>공시가격(HUG 기준)</b>으로 깡통전세 위험을 판정합니다.
      </p>

      <div className="kkt-area">
        <div ref={mapEl} className="kkt-map" />

        {/* 지도 위 상단: 지역 드롭다운 + 주소검색 일체화 */}
        <div className="kkt-top">
          <div className="kkt-region">
            <select value={sido} onChange={(e) => setSido(e.target.value)}><option value="">시·도</option>{sidos.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}</select>
            <select value={sigungu} onChange={(e) => setSigungu(e.target.value)} disabled={!sido}><option value="">시·군·구</option>{sigungus.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}</select>
            <select value={dong} onChange={(e) => setDong(e.target.value)} disabled={!sigungu}><option value="">읍·면·동</option>{dongs.map((d) => <option key={d.code} value={d.code}>{d.name}</option>)}</select>
          </div>
          <div className="kkt-addr">
            <input value={addr} onChange={(e) => setAddr(e.target.value)} onKeyDown={(e) => e.key === "Enter" && searchAddr()} placeholder="주소 검색 (예: 화곡동 102-119)" />
            <button onClick={searchAddr} aria-label="검색"><Search size={15} /></button>
          </div>
        </div>

        <div className="kkt-status">{status || "지도를 움직여 빌라를 찾아보세요"}</div>

        {/* 우측 사이드바: 평형 선택 + 점검 결과 */}
        {(sel || loading) && (
          <aside className="kkt-side">
            <button className="kkt-side-x" onClick={() => { setSel(null); setRes(null); if (pinRef.current) { pinRef.current.setMap(null); pinRef.current = null; } document.querySelectorAll(".jvm.on").forEach((e) => e.classList.remove("on")); }}><X size={15} /></button>
            {sel && <div className="kkt-bld"><Home size={14} /> <b>{res?.resolved?.building || sel.name}</b>{sel.tx_count != null && <span> · 실거래 {sel.tx_count}건</span>}</div>}
            {loading && <div className="jc-hint">공시가격 조회 중…</div>}
            {res && !res.ok && <div className="jc-err">{res.error}</div>}

            {res?.ok && res.units && res.units.length > 0 && (() => {
              const isHouse = !!res.resolved?.kind?.includes("단독") || res.units.some((u) => u.whole);
              // 단독·다가구: 판정하지 않고 알림 + 공시가격(참고)만. 빌라(공동주택): 면적선택→판정.
              return isHouse ? (
                <>
                  <div className="kkt-warn"><AlertTriangle size={13} /> 단독·다가구는 한 건물에 <b>여러 세입자 보증금이 누적</b>되는 구조라 공시가격만으로는 깡통 여부를 <b>판정하지 않습니다</b>. 아래는 참고용이며, <b>전입세대 열람원·확정일자 부여현황</b>으로 선순위 보증금 총액을 꼭 확인하세요.</div>
                  <div className="kkt-gongsi" style={{ marginTop: 8 }}>
                    <div className="jc-gongsi-row"><span>건물 전체 공시가격 (개별주택가격)</span><b>{won(res.units![0].gongsi)}</b></div>
                    <div className="jc-gongsi-row hug"><span>HUG 보증한도 (공시가×126%, 참고)</span><b>{won(res.units![0].hug_limit)}</b></div>
                  </div>
                </>
              ) : (
                <>
                  <div className="kkt-label">전용면적 선택 <span>면적마다 공시가격이 달라요</span></div>
                  <div className="jc-units">
                    {res.units!.map((u) => (
                      <button key={u.area_m2 ?? "w"} className={`jc-unit ${unit?.area_m2 === u.area_m2 ? "on" : ""}`} onClick={() => setUnit(u)}>
                        <b>{u.area_m2 == null ? "건물 전체" : `${u.area_m2}㎡`}</b><span>{won(u.gongsi)}</span>
                      </button>
                    ))}
                  </div>
                  {unit && (
                    <div className="kkt-gongsi">
                      <div className="jc-gongsi-row"><span>공시가격 (전용 {unit.area_m2}㎡)</span><b>{won(unit.gongsi)}</b></div>
                      <div className="jc-gongsi-row hug"><span>HUG 보증한도 (공시가×126%)</span><b>{won(unit.hug_limit)}</b></div>
                      <div className="jc-depbox"><input type="number" value={dep} onChange={(e) => setDep(e.target.value)} placeholder="전세 보증금 (만원)" autoFocus /></div>
                      {dep && <div className="muted" style={{ fontSize: 11.5 }}>{won(depWon)}</div>}
                      <div className="jc-depbox" style={{ marginTop: 8 }}><input type="number" value={lien} onChange={(e) => setLien(e.target.value)} placeholder="선순위 채권 (근저당·대출, 만원)" /></div>
                      <div className="muted" style={{ fontSize: 10.5 }}>{lienWon ? won(lienWon) + " · " : ""}등기부등본 '채권최고액' 합계 · 없으면 0</div>
                    </div>
                  )}
                  {v && (
                    <div className="kkt-verdict" style={{ borderColor: GRADE[v.grade].c, background: `${GRADE[v.grade].c}12` }}>
                      <div className="jc-vhead" style={{ color: GRADE[v.grade].c }}>
                        {(() => { const I = GRADE[v.grade].icon; return <I size={24} />; })()}
                        <span className="jc-grade">{v.grade}</span><span className="jc-ratio">{lienWon ? "부채비율" : "전세가율"} {v.ratio}%</span>
                      </div>
                      <div className="jc-vmsg">{v.msg}</div>
                      {lienWon > 0 && unit && <div className="kkt-break">전세 {won(depWon)} + 선순위채권 {won(lienWon)} = <b>{won(totalWon)}</b> · 보증한도 {won(unit.hug_limit)}</div>}
                      <div className="jc-gauge"><div className="jc-gauge-fill" style={{ width: `${Math.min(v.ratio / 1.6, 100)}%`, background: GRADE[v.grade].c }} /><span className="jc-gauge-100">126%</span><span className="jc-gauge-140">140%</span></div>
                    </div>
                  )}
                </>
              );
            })()}
            {res?.ok && (!res.units || res.units.length === 0) && srvV && (
              <div className="kkt-gongsi">
                <div className="jc-gongsi-row"><span>공시가격 · {res.resolved?.kind}</span><b>{won(srvV.gongsi)}</b></div>
                <div className="jc-gongsi-row hug"><span>HUG 한도 ×140%</span><b>{won(srvV.hug_limit)}</b></div>
              </div>
            )}

            {/* 이 건물 실거래 */}
            {res?.ok && res.building_deals && (res.building_deals.sales.length > 0 || res.building_deals.rents.length > 0) && (
              <>
                <div className="kkt-label">이 건물 실거래</div>
                <div className="kkt-deals">
                  {res.building_deals.sales.slice(0, 3).map((s, i) => (
                    <div className="kkt-deal" key={"s" + i}><span className="t sale">매매</span><span className="d">{s.date}</span><span className="a">{s.area_m2}㎡{s.floor ? `·${s.floor}층` : ""}</span><b>{won(s.amount)}</b></div>
                  ))}
                  {res.building_deals.rents.slice(0, 4).map((r, i) => (
                    <div className="kkt-deal" key={"r" + i}><span className={`t ${r.monthly ? "wol" : "jeon"}`}>{r.monthly ? "월세" : "전세"}</span><span className="d">{r.date}</span><span className="a">{r.area_m2}㎡{r.floor ? `·${r.floor}층` : ""}</span><b>{won(r.deposit)}{r.monthly ? `/${won(r.monthly)}` : ""}</b></div>
                  ))}
                </div>
              </>
            )}

            {/* 현재 매물 — 네이버 바로가기 */}
            {res?.ok && res.building_listings && res.building_listings.length > 0 && (
              <>
                <div className="kkt-label">현재 매물 {res.building_listings.length}건</div>
                <div className="kkt-listings">
                  {res.building_listings.slice(0, 6).map((l) => (
                    <button className="kkt-listing" key={l.article_no} onClick={() => openListingPopup(l.naver_url)}>
                      <span className="kkt-l-t">{l.trade}</span>
                      <span className="kkt-l-m">{l.area_m2}㎡{l.dup && l.dup > 1 ? ` · ${l.dup}곳` : ""}</span>
                      {l.grade && GRADE[l.grade] && <span className="kkt-l-g" style={{ background: GRADE[l.grade].c + "1f", color: GRADE[l.grade].c }}>{l.grade} {l.ratio}%</span>}
                      <b>{won(l.price)}{l.trade === "월세" && l.rent ? `/${won(l.rent)}` : ""}</b>
                      <ExternalLink size={12} className="kkt-l-x" />
                    </button>
                  ))}
                </div>
              </>
            )}

            {res?.ok && res.nearby && (
              <>
                <div className="kkt-label">{res.nearby.scope} 시세 <span>이 건물 아닌 동네 평균</span></div>
                <div className="kkt-near">
                  <div><span>매매 중위</span><b>{won(res.nearby.sale_median)}</b></div>
                  <div><span>전세 중위</span><b>{won(res.nearby.jeonse_median)}</b></div>
                  <div><span>위험건물 비율</span><b className={(res.nearby.risky_pct || 0) >= 30 ? "danger" : ""}>{res.nearby.risky_pct ?? "-"}%</b></div>
                </div>
                {res.nearby.risky_pct != null && <div className="muted" style={{ fontSize: 10.5, marginTop: 5 }}>이 동네 빌라 중 전세가율 80% 이상(깡통 위험) 비율</div>}
              </>
            )}
            {res?.ok && <p className="muted" style={{ fontSize: 11, marginTop: 10, lineHeight: 1.5 }}>※ <b>공시가격 기준 단순 추정</b>입니다. 실제 HUG 가입 여부는 KB시세·부동산테크 시세·<b>선순위채권·근저당</b>·주택유형에 따라 달라질 수 있어요. 계약 전 <b>등기부등본</b> 확인 필수.</p>}
          </aside>
        )}
      </div>
    </div>
  );
}
