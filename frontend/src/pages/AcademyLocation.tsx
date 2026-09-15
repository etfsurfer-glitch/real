import { useEffect, useRef, useState, useCallback, type ReactNode } from "react";
import { MapPin, TrendingUp, Users, Building2, X, ZoomOut } from "lucide-react";
import { useAuth } from "../auth";
import { loadKakao, attachMapControls } from "../lib/kakaomap";
import { brokerageFee } from "../lib/buycalc";

const API = import.meta.env.VITE_API_BASE;

// 개업 추천 등급 색(초록=좋음 → 빨강=경쟁과잉). tx-map(빨강하락/파랑상승)과 구분.
const GRADE_COLOR: Record<string, string> = {
  S: "#0f7a3d", A: "#28a745", B: "#e0a11e", C: "#e8712e", D: "#c0392b",
};
// 임대차 중개보수 상한요율(환산보증금 기준). buycalc BROKERAGE 의 임대판.
const LEASE = [
  { max: 5e7, pm: 5, lim: 20e4 }, { max: 1e8, pm: 4, lim: 30e4 },
  { max: 6e8, pm: 3, lim: null }, { max: 12e8, pm: 4, lim: null },
  { max: 15e8, pm: 5, lim: null }, { max: Infinity, pm: 6, lim: null },
] as const;
function leaseFee(p: number): number {
  for (const b of LEASE) if (p < b.max) { const f = Math.floor((p * b.pm) / 1000); return b.lim ? Math.min(f, b.lim) : f; }
  return 0;
}
const man = (v: number) => `${Math.round(v / 1e4).toLocaleString()}만`;
const eok = (v: number) => `${(v / 1e8).toFixed(1)}억`;

type Metric = {
  code: string; name: string; level: string; grade?: string; score?: number;
  agents: number; agents_eff: number; sale_n: number; lease_n: number;
  sale_avg: number; lease_avg: number; m_sale: number; m_lease: number;
  per_agent_tx: number; turnover: number | null; lat: number; lng: number;
  cost_defaults?: { rent: number; staff: number; ad: number; assoc: number };
  cost_src?: string;
  upcoming?: { dong_hh: number; dong_n: number; sgg_hh: number; sgg_n: number };
  benchmarks?: { n: number; top1: number; top10: number; median: number; avg: number; my_top_pct?: number };
  coef?: { success_sale: number; success_lease: number; both_side: number };
  sim?: { profit: number; revenue: number; cost: number;
    est_lease_deals?: number; est_sale_deals?: number; fee_note?: string;
    costs?: { rent: number; staff: number; ad: number; assoc: number } };
  mode?: string; stock_lease?: number; stock_sale?: number; turn_days?: number | null; m_total?: number; sale_n12?: number;
  m_new?: number; no_premium_rate?: number; rent_trend?: number;
  upcoming_hh?: number;
};

export default function AcademyLocation() {
  const { token } = useAuth();
  const elRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const ovsRef = useRef<any[]>([]);
  const keyRef = useRef("");
  const [sel, setSel] = useState<Metric | null>(null);
  const [mode, setMode] = useState<"gu" | "dong" | "complex">("gu");
  const [err, setErr] = useState("");
  // 지도 상태 오버레이 — 뷰포트/줌에 따라 결과가 없을 때 사용자가 멈추지 않게 안내.
  const [overlay, setOverlay] = useState<{ kind: "loading" | "empty"; msg: string } | null>(
    { kind: "loading", msg: "지역 데이터를 불러오는 중…" });

  // 상세(수익 시뮬) — 슬라이더/비용은 로컬 state 로 즉시계산
  const [occ, setOcc] = useState(1.0);
  const [cost, setCost] = useState({ rent: 0, staff: 0, ad: 0, assoc: 0 });
  // 업종 모드: 주거 전문 / 상업 전문(상가+사무실 통합 — 2026-09-04 사용자 결정)
  const [biz, setBiz] = useState<"resi" | "comm">("resi");
  const bizRef = useRef<"resi" | "comm">("resi");
  const idleFnRef = useRef<() => void>(() => {});
  const switchBiz = (b: "resi" | "comm") => {
    if (bizRef.current === b) return;
    bizRef.current = b; setBiz(b); setSel(null);
    keyRef.current = "";                      // bbox 캐시 무효화 → 즉시 재조회
    idleFnRef.current();
  };

  const openDetail = useCallback((level: string, id: string) => {
    if (!API || !token) return;
    fetch(`${API}/admin/academy/detail?level=${level}&id=${encodeURIComponent(id)}`,
      { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
      .then((m: Metric) => {
        setSel(m); setOcc(1.0);
        setCost(m.cost_defaults || { rent: 0, staff: 0, ad: 0, assoc: 0 });
      }).catch((e) => setErr(String(e)));
  }, [token]);

  useEffect(() => {
    if (!API || !token) return;
    let dead = false;
    loadKakao().then(() => {
      if (dead || !elRef.current) return;
      const kakao = (window as any).kakao;

      const render = (items: Metric[], gLevel: string) => {
        const m = mapRef.current; if (!m) return;
        ovsRef.current.forEach((o) => o.setMap(null)); ovsRef.current = [];
        for (const it of items) {
          const el = document.createElement("div");
          const col = GRADE_COLOR[it.grade || "C"] || "#888";
          const isPin = gLevel === "complex";
          Object.assign(el.style, {
            background: col, color: "#fff", borderRadius: isPin ? "9px" : "999px",
            padding: isPin ? "4px 8px" : "5px 11px", fontWeight: "800", cursor: "pointer",
            boxShadow: "0 2px 8px rgba(0,0,0,.28)", border: "1.5px solid rgba(255,255,255,.7)",
            fontSize: isPin ? "11.5px" : "12.5px", whiteSpace: "nowrap", textAlign: "center",
            lineHeight: "1.25",
          });
          const profit = it.sim ? it.sim.profit : 0;
          const up = it.upcoming_hh || 0;
          el.innerHTML = `<div>${aggName(it.name)}</div>`
            + `<div style="font-size:10.5px;font-weight:700;opacity:.95">${it.grade || ""} · ${man(profit)}</div>`
            + (up > 0 ? `<div style="margin-top:2px;background:rgba(255,255,255,.92);color:#0f7a3d;`
              + `border-radius:6px;padding:1px 6px;font-size:10px;font-weight:800;letter-spacing:-.2px">`
              + `입주예정 ${up.toLocaleString()}세대</div>` : "");
          el.addEventListener("click", (e) => {
            e.stopPropagation();
            if (gLevel === "gu") m.setLevel(6, { anchor: new kakao.maps.LatLng(it.lat, it.lng) });
            else if (bizRef.current !== "resi") {
              // 상업(Phase 0): 스냅샷에 지표·sim이 이미 확정 — 상세 API 없이 즉시 패널
              setSel(it); setOcc(1.0);
              setCost(it.sim?.costs || { rent: 0, staff: 0, ad: 0, assoc: 0 });
            }
            else openDetail(gLevel, it.code);
          });
          const ov = new kakao.maps.CustomOverlay({
            position: new kakao.maps.LatLng(it.lat, it.lng), content: el, yAnchor: 0.5, zIndex: 5,
          });
          ov.setMap(m); ovsRef.current.push(ov);
        }
      };

      const onIdle = () => {
        const m = mapRef.current; if (!m) return;
        const lvl = m.getLevel();
        const bz = bizRef.current;
        let gLevel: "gu" | "dong" | "complex" = lvl >= 8 ? "gu" : lvl >= 5 ? "dong" : "complex";
        if (bz !== "resi" && gLevel === "complex") gLevel = "dong";   // 상업은 동이 최소 단위
        setMode(gLevel);
        const bb = m.getBounds(); const sw = bb.getSouthWest(), ne = bb.getNorthEast();
        const qs = new URLSearchParams({
          level: gLevel, mode: bz,
          min_n: bz !== "resi" ? "10" : gLevel === "gu" ? "8" : gLevel === "dong" ? "3" : "1",
          sw_lat: String(sw.getLat()), sw_lng: String(sw.getLng()),
          ne_lat: String(ne.getLat()), ne_lng: String(ne.getLng()),
        });
        const key = `${bz}:${gLevel}:${sw.getLat().toFixed(2)},${sw.getLng().toFixed(2)},${ne.getLat().toFixed(2)},${ne.getLng().toFixed(2)}`;
        if (key === keyRef.current) return;
        keyRef.current = key;
        setOverlay({ kind: "loading", msg: "지역 데이터를 불러오는 중…" });
        fetch(`${API}/admin/academy/map?${qs}`, { headers: { Authorization: `Bearer ${token}` } })
          .then((r) => { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
          .then((d) => {
            if (keyRef.current !== key) return;
            const items = d.items || [];
            render(items, gLevel);
            if (items.length) setOverlay(null);
            else setOverlay({ kind: "empty",
              msg: gLevel === "complex"
                ? "이 화면엔 거래 있는 단지가 없어요 — 지도를 조금 축소하거나 이동해 보세요"
                : gLevel === "dong"
                  ? "이 화면엔 표시할 동이 없어요 — 지도를 이동하거나 축소해 보세요"
                  : "표시할 지역이 없어요 — 지도를 이동해 보세요" });
          })
          .catch((e) => { setErr(String(e)); setOverlay(null); });
      };
      idleFnRef.current = onIdle;

      mapRef.current = new kakao.maps.Map(elRef.current, {
        center: new kakao.maps.LatLng(37.55, 127.0), level: 9,
      });
      attachMapControls(mapRef.current, elRef.current);
      kakao.maps.event.addListener(mapRef.current, "idle", onIdle);
      onIdle();
    });
    return () => { dead = true; };
  }, [token, openDetail]);

  // 실시간 수익 계산(클라이언트) — 백엔드 academy.revenue_sim 과 동일 산식
  const sim = sel && sel.mode ? (() => {           // 상업: 서버 확정 sim × 점유율
    const base = sel.sim!;
    const rev = base.revenue * occ;
    const cst = (cost.rent || 0) + (cost.staff || 0) + (cost.ad || 0) + (cost.assoc || 0);
    return { estSale: (base.est_sale_deals || 0) * occ, estLease: (base.est_lease_deals || 0) * occ,
      rev, cost: cst, profit: rev - cst };
  })() : sel && sel.coef ? (() => {
    const c = sel.coef!;
    const estSale = (sel.m_sale * c.success_sale) / sel.agents_eff * occ;
    const estLease = (sel.m_lease * c.success_lease) / sel.agents_eff * occ;
    const rev = estSale * brokerageFee(sel.sale_avg) * c.both_side
      + estLease * leaseFee(sel.lease_avg) * c.both_side;
    const cst = (cost.rent || 0) + (cost.staff || 0) + (cost.ad || 0) + (cost.assoc || 0);
    return { estSale, estLease, rev, cost: cst, profit: rev - cst };
  })() : null;

  return (
    <div style={{ position: "relative", height: "calc(100vh - 52px)", overflow: "hidden" }}>
      <div ref={elRef} style={{ width: "100%", height: "100%" }} />

      {/* 상단 안내 */}
      <div style={{ position: "absolute", top: 12, left: 12, zIndex: 10, background: "rgba(255,255,255,.94)",
        borderRadius: 12, padding: "10px 14px", boxShadow: "0 4px 16px rgba(0,0,0,.14)", maxWidth: 320 }}>
        <div style={{ fontWeight: 800, fontSize: 15, display: "flex", alignItems: "center", gap: 6 }}>
          <MapPin size={17} /> 개업 입지 · 수익 지도
        </div>
        <div style={{ display: "flex", gap: 5, marginTop: 8 }}>
          {([["resi", "주거 전문"], ["comm", "상업 전문 (상가·사무실)"]] as const).map(([v, t]) => (
            <button key={v} onClick={() => switchBiz(v)}
              style={{ flex: 1, padding: "6px 0", borderRadius: 8, fontSize: 12, fontWeight: 800, cursor: "pointer",
                border: `1.5px solid ${biz === v ? "var(--c-primary)" : "var(--c-border)"}`,
                background: biz === v ? "var(--c-primary)" : "#fff",
                color: biz === v ? "#fff" : "var(--c-text)" }}>{t}</button>
          ))}
        </div>
        <div style={{ fontSize: 12.5, color: "var(--c-muted)", marginTop: 4 }}>
          현재 <b>{mode === "gu" ? "시·군·구" : mode === "dong" ? "읍·면·동" : "아파트 단지"}</b> 보기 · 확대할수록 세밀 · 색=개업 등급(초록↑)
        </div>
        <Legend />
      </div>
      {err && <div style={{ position: "absolute", top: 12, right: 12, zIndex: 11, background: "#fff0f0",
        color: "crimson", padding: "6px 10px", borderRadius: 8, fontSize: 12 }}>오류 {err}</div>}

      {/* 지도 상태 오버레이 — 로딩/결과없음 안내(지도 조작은 막지 않음) */}
      {overlay && (
        <div style={{ position: "absolute", left: "50%", top: "46%", transform: "translate(-50%,-50%)",
          zIndex: 9, pointerEvents: "none", display: "flex", alignItems: "center", gap: 10,
          background: "rgba(17,28,44,.86)", color: "#eef5ff", padding: "12px 18px",
          borderRadius: 12, fontSize: 14.5, fontWeight: 700, letterSpacing: "-0.3px",
          boxShadow: "0 8px 24px rgba(0,0,0,.28)", maxWidth: "min(86vw, 420px)", textAlign: "center" }}>
          {overlay.kind === "loading" ? (
            <span style={{ width: 16, height: 16, flex: "none", borderRadius: "50%",
              border: "2.5px solid rgba(255,255,255,.35)", borderTopColor: "#fff",
              animation: "acad-spin .8s linear infinite" }} />
          ) : (
            <ZoomOut size={18} style={{ flex: "none", opacity: .9 }} />
          )}
          <span>{overlay.msg}</span>
          <style>{`@keyframes acad-spin{to{transform:rotate(360deg)}}`}</style>
        </div>
      )}

      {/* 상세 패널 */}
      {sel && (
        <div style={{ position: "absolute", top: 0, right: 0, bottom: 0, width: "min(400px, 92vw)", zIndex: 20,
          background: "#fff", boxShadow: "-6px 0 24px rgba(0,0,0,.18)", overflowY: "auto", padding: "18px 18px 40px" }}>
          <button onClick={() => setSel(null)} style={{ position: "absolute", top: 12, right: 12, border: 0,
            background: "#f1f3f6", borderRadius: 8, width: 32, height: 32, cursor: "pointer" }}><X size={17} /></button>
          <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
            <span style={{ background: GRADE_COLOR[sel.grade || "C"], color: "#fff", fontWeight: 900,
              borderRadius: 9, width: 40, height: 40, display: "grid", placeItems: "center", fontSize: 20 }}>{sel.grade}</span>
            <div>
              <div style={{ fontWeight: 800, fontSize: 18 }}>{sel.name}</div>
              <div style={{ fontSize: 12.5, color: "var(--c-muted)" }}>
                {sel.mode ? "상업(상가·사무실) · 읍·면·동"
                  : sel.level === "complex" ? "아파트 단지" : "읍·면·동"} · 입지점수 {sel.score ?? "-"}
              </div>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, margin: "16px 0" }}>
            {sel.mode ? (<>
              <Stat icon={<TrendingUp size={15} />} k="임대 광고 스톡" v={`${(sel.stock_lease ?? 0).toLocaleString()}건`} />
              <Stat icon={<TrendingUp size={15} />} k="연 매매 실거래" v={`${(sel.sale_n12 ?? 0).toLocaleString()}건 ${sel.sale_avg ? `(평${eok(sel.sale_avg)})` : ""}`} />
              <Stat icon={<Users size={15} />} k="취급 중개사" v={`${sel.agents}곳`} />
              <Stat icon={<Building2 size={15} />} k="재고 회전일수" v={sel.turn_days ? `${sel.turn_days}일` : "-"} />
              <Stat icon={<TrendingUp size={15} />} k="월 성사 추정" v={`${sel.m_total}건`} />
              <Stat icon={<TrendingUp size={15} />} k="무권리 표기(상가)"
                v={`${Math.round((sel.no_premium_rate || 0) * 100)}%`} />
            </>) : (<>
              <Stat icon={<TrendingUp size={15} />} k="연 매매" v={`${sel.sale_n}건 (평${eok(sel.sale_avg)})`} />
              <Stat icon={<TrendingUp size={15} />} k="연 전월세" v={`${sel.lease_n}건`} />
              <Stat icon={<Users size={15} />} k="주거취급 중개사" v={`${sel.agents}곳`} />
              <Stat icon={<Building2 size={15} />} k="1인당 월거래" v={`${sel.per_agent_tx}건`} />
            </>)}
          </div>

          {/* 미래 수요 — 입주예정물량(있을 때만). 큰 물량은 선점 개업 시그널 */}
          {sel.upcoming && (sel.upcoming.dong_hh > 0 || sel.upcoming.sgg_hh > 0) && (
            <div style={{ background: sel.upcoming.dong_hh >= 1000 ? "#e9f8ef" : "var(--c-row-stripe)",
              border: sel.upcoming.dong_hh >= 1000 ? "1px solid #bfe8cd" : "1px solid var(--c-border-soft)",
              borderRadius: 12, padding: "11px 13px", marginBottom: 14 }}>
              <div style={{ fontSize: 12, fontWeight: 800, color: sel.upcoming.dong_hh >= 1000 ? "#0f7a3d" : "var(--c-text-soft)",
                display: "flex", alignItems: "center", gap: 5 }}>
                <Building2 size={14} /> 입주예정(향후 24개월)
                {sel.upcoming.dong_hh >= 1000 && <span style={{ background: "#0f7a3d", color: "#fff",
                  borderRadius: 999, padding: "1px 8px", fontSize: 10.5 }}>수요 급증 예정</span>}
              </div>
              <div style={{ fontSize: 13.5, fontWeight: 700, marginTop: 5 }}>
                {sel.upcoming.dong_hh > 0 && <>이 동 <b>{sel.upcoming.dong_hh.toLocaleString()}세대</b> ({sel.upcoming.dong_n}개 단지)</>}
                {sel.upcoming.dong_hh > 0 && sel.upcoming.sgg_hh > sel.upcoming.dong_hh && " · "}
                {sel.upcoming.sgg_hh > sel.upcoming.dong_hh && <>시군구 전체 {sel.upcoming.sgg_hh.toLocaleString()}세대</>}
              </div>
              <div style={{ fontSize: 11, color: "var(--c-faint)", marginTop: 3 }}>한국부동산원 입주예정물량 (반기 갱신)</div>
            </div>
          )}

          {/* 수익 시뮬레이터 */}
          <div style={{ background: "var(--c-primary-tint)", borderRadius: 14, padding: 16 }}>
            <div style={{ fontWeight: 800, fontSize: 15, marginBottom: 10 }}>개업 수익 시뮬레이션</div>

            <label style={{ fontSize: 12.5, fontWeight: 700, color: "var(--c-text-soft)" }}>
              점유율(신규 {occ < 0.8 ? "보수" : occ > 1.2 ? "공격" : "안착"}) · {occ.toFixed(1)}×
            </label>
            <input type="range" min={0.4} max={1.5} step={0.1} value={occ}
              onChange={(e) => setOcc(parseFloat(e.target.value))} style={{ width: "100%", margin: "6px 0 12px" }} />

            {(["rent", "staff", "ad", "assoc"] as const).map((k) => (
              <div key={k} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 7 }}>
                <span style={{ fontSize: 12.5, color: "var(--c-text-soft)" }}>{COST_LABEL[k]}</span>
                <input type="number" value={Math.round((cost[k] || 0) / 1e4)} step={10}
                  onChange={(e) => setCost({ ...cost, [k]: Math.max(0, parseInt(e.target.value || "0", 10)) * 1e4 })}
                  style={{ width: 90, textAlign: "right", border: "1px solid var(--c-border)", borderRadius: 7,
                    padding: "5px 8px", fontSize: 13 }} />
              </div>
            ))}
            <div style={{ fontSize: 11, color: "var(--c-faint)", textAlign: "right", marginTop: -2 }}>
              단위: 만원/월{sel.cost_src ? ` · 임대료 제안 = ${sel.cost_src}` : ""}
            </div>

            {sim && (
              <div style={{ marginTop: 14, borderTop: "1px dashed var(--c-border)", paddingTop: 12 }}>
                <Row k="예상 월매출" v={man(sim.rev)} />
                <Row k="예상 월거래" v={`매매 ${sim.estSale.toFixed(1)} · 임대 ${sim.estLease.toFixed(1)}건`} muted />
                <Row k="월 고정비" v={`− ${man(sim.cost)}`} muted />
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline",
                  marginTop: 8, paddingTop: 8, borderTop: "1px solid var(--c-border)" }}>
                  <b style={{ fontSize: 14 }}>예상 월 순이익</b>
                  <b style={{ fontSize: 22, color: sim.profit >= 0 ? "var(--c-wolse)" : "var(--c-sale)" }}>
                    {sim.profit >= 0 ? "+" : "−"}{man(Math.abs(sim.profit))}</b>
                </div>

                {/* 전국 참고치 — 같은 레벨(동끼리/단지끼리) 예상 순이익 분포 구간 */}
                {sel.benchmarks && (
                  <div style={{ marginTop: 10, background: "rgba(18,104,211,.06)", borderRadius: 10,
                    padding: "9px 12px" }}>
                    <div style={{ fontSize: 11.5, fontWeight: 800, color: "var(--c-text-soft)", marginBottom: 5 }}>
                      전국 {sel.level === "complex" ? "단지" : "동"} 순이익 참고치
                      {sel.benchmarks.my_top_pct != null &&
                        <span style={{ color: "var(--c-primary)", marginLeft: 6 }}>
                          · 이 지역 = 상위 {sel.benchmarks.my_top_pct}%</span>}
                    </div>
                    {([["상위 1%", sel.benchmarks.top1], ["상위 10%", sel.benchmarks.top10],
                       ["중앙값", sel.benchmarks.median], ["평균", sel.benchmarks.avg]] as const).map(([k, v]) => (
                      <div key={k} style={{ display: "flex", justifyContent: "space-between",
                        fontSize: 12, color: "var(--c-muted)", marginBottom: 2 }}>
                        <span>{k}</span>
                        <span style={{ fontWeight: 700, color: v >= 0 ? "var(--c-text-soft)" : "var(--c-sale)" }}>
                          {v >= 0 ? "+" : "−"}{man(Math.abs(v))}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
          <p style={{ fontSize: 11, color: "var(--c-faint)", marginTop: 12, lineHeight: 1.5 }}>
            {sel.mode
              ? <>※ 매매는 국토부 상업업무용 <b>실거래</b>(최근 12개월, 동명 매칭 ~75%), 임대는 실거래
                신고가 없어 <b>광고 흐름(등록·소멸) 기반 추정치</b>입니다. 광고 소멸에는 만료·회수가
                섞여 있어 임대 성사율 12%·보수 실수취 70%(상한 0.9% 협의)의 보수적 가정을 적용했으며,
                수익을 보장하지 않습니다.</>
              : <>※ 최근 12개월 실거래·활성 중개사 기반 <b>추정치</b>이며 수익을 보장하지 않습니다.
                매매·전월세만 반영(상가·오피스텔 제외), 지역 중개사 경유·양타 가정 포함.</>}
          </p>
        </div>
      )}
    </div>
  );
}

const COST_LABEL: Record<string, string> = { rent: "임대료", staff: "인건비", ad: "광고·마케팅", assoc: "공제·협회비" };
function aggName(n: string) { return (n || "").split(" ").slice(-1)[0] || n; }

function Legend() {
  return (
    <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
      {(["S", "A", "B", "C", "D"] as const).map((g) => (
        <span key={g} style={{ display: "flex", alignItems: "center", gap: 3, fontSize: 11, fontWeight: 700 }}>
          <i style={{ width: 11, height: 11, borderRadius: 3, background: GRADE_COLOR[g], display: "inline-block" }} />{g}
        </span>
      ))}
    </div>
  );
}
function Stat({ icon, k, v }: { icon: ReactNode; k: string; v: string }) {
  return (
    <div style={{ background: "var(--c-row-stripe)", borderRadius: 10, padding: "9px 11px" }}>
      <div style={{ fontSize: 11.5, color: "var(--c-muted)", display: "flex", alignItems: "center", gap: 4 }}>{icon}{k}</div>
      <div style={{ fontWeight: 800, fontSize: 14, marginTop: 3 }}>{v}</div>
    </div>
  );
}
function Row({ k, v, muted }: { k: string; v: string; muted?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", fontSize: muted ? 12.5 : 13.5,
      color: muted ? "var(--c-muted)" : "var(--c-text)", marginBottom: 4 }}>
      <span>{k}</span><span style={{ fontWeight: muted ? 600 : 800 }}>{v}</span>
    </div>
  );
}
