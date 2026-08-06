// 아파트매수마법사 v2 (관리자 가오픈) — 레퍼런스(zento 구입비용 계산기) 번들 분석 후
// 동일 산식·입력 의미로 복제: 원 단위 입력+퀵버튼은 '+누적 증가', 방공제·계약금비율·
// 시가표준액·실무비용 프리셋·단계별 흐름도까지. 계산은 전부 클라이언트 즉시(lib/buycalc).
// 콕집 차별화 = 하단 '이 조건으로 살 수 있는 단지 찾기' (매물×실거래 추천, 서버는 후보만).
import { useEffect, useMemo, useState } from "react";
import FavHeart from "../components/FavHeart";
import { Link } from "react-router-dom";
import {
  Wand2, Calculator, ChevronLeft, ChevronRight, ChevronDown, ChevronUp,
  Loader2, Building2, RotateCcw, Info, X, MapPin,
  Landmark, Wallet, Receipt, Home, KeyRound, Share2,
} from "lucide-react";
import { useAuth } from "../auth";
import { useStickyState } from "../hooks/useStickyState";
import {
  CalcInput, DEFAULT_INPUT, calculate, maxAffordablePrice, defenseFundAmount,
  brokerageFee, lawyerFee, loanRegulation, effectiveLoan, INTERIOR,
  STAGE_LABEL, STAGE_ORDER, fmtWon, fmtEok,
} from "../lib/buycalc";
import { areaLabel } from "../lib/area";
import { classifyRegion } from "../lib/buyregion";

const API_BASE = import.meta.env.VITE_API_BASE;
const PRIMARY = "#1268d3";
const BORDER = "#e4e9f0";
const GREEN = "#1f9d63";
const RED = "#d23b3b";
const SPIN: React.CSSProperties = { animation: "hp-spin .8s linear infinite" };
const PBTN: React.CSSProperties = {
  background: PRIMARY, color: "#fff", border: "none",
  borderRadius: 10, fontWeight: 700, cursor: "pointer",
};
const CARD: React.CSSProperties = {
  border: `1px solid ${BORDER}`, borderRadius: 14, padding: 16, background: "#fff",
};

// 퀵버튼 — 레퍼런스와 동일 금액·+누적 의미
const Q_SALE = [{ l: "+3억", v: 3e8 }, { l: "+5억", v: 5e8 }, { l: "+7억", v: 7e8 }, { l: "+10억", v: 1e9 }];
const Q_LOAN = [{ l: "+1억", v: 1e8 }, { l: "+2억", v: 2e8 }, { l: "+3억", v: 3e8 }, { l: "+5억", v: 5e8 }];
const Q_CASH = [{ l: "+5천만", v: 5e7 }, { l: "+1억", v: 1e8 }, { l: "+1.5억", v: 15e7 }, { l: "+2억", v: 2e8 }];
const Q_MGMT = [{ l: "+50만", v: 5e5 }, { l: "+100만", v: 1e6 }, { l: "+200만", v: 2e6 }];
const RT_LABEL: Record<string, string> = {
  seoul: "서울", overconcentration: "과밀억제권역", metro: "광역시", other: "기타 지방",
};

type Region = { code: string; name: string };
type Candidate = {
  complex_no: string; complex_name: string; region: string | null;
  area_name: string; excl: number | null; min_ask: number; n_ask: number;
  tx_avg: number | null; tx_n: number; households: number | null; approve_ymd: string | null;
};

export default function BuyWizard() {
  const { token } = useAuth();
  // 입력·단계·지역·후보결과는 localStorage 유지 — 단지 이동/뒤로가기·새로고침에도 복원
  const [inpRaw, setInp] = useStickyState<CalcInput>("buywiz:inp", DEFAULT_INPUT);
  const inp = useMemo(() => ({ ...DEFAULT_INPUT, ...inpRaw }), [inpRaw]);   // 스키마 확장 대비 기본값 보강
  const [mode, setMode] = useStickyState<"ask" | "wizard" | "direct">("buywiz:mode", "ask");
  const [step, setStep] = useStickyState("buywiz:step", 0);
  const set = (patch: Partial<CalcInput>) => setInp((s) => ({ ...s, ...patch }));

  const res = useMemo(() => calculate(inp), [inp]);
  const ok = res.cashGap >= 0;
  const reg = useMemo(() => loanRegulation(inp), [inp]);
  const loanOver = !reg.banned && inp.loanAmount > reg.maxLoan;

  // ---- 추천 섹션 상태 ----
  const [sidos, setSidos] = useState<Region[]>([]);
  const [sggs, setSggs] = useState<Region[]>([]);
  const [sido, setSido] = useStickyState("buywiz:sido", "");
  const [sigungus, setSigungus] = useState<Region[]>([]);
  const [sgg, setSgg] = useStickyState<Region | null>("buywiz:sgg", null);   // 매수 예상 시군구(단일) — 규제 판정 기준
  const cls = useMemo(() => (sido && sgg ? classifyRegion(sido, sgg.code) : null), [sido, sgg]);
  const [areaBand, setAreaBand] = useStickyState<[number, number]>("buywiz:areaBand", [59, 85]);
  const [cands, setCands] = useStickyState<Candidate[] | null>("buywiz:cands", null);
  const [candLimit, setCandLimit] = useStickyState("buywiz:candLimit", 30);   // 더보기로 확장
  const [maxP, setMaxP] = useStickyState("buywiz:maxP", 0);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/stats/changes/sido-list`).then((r) => r.json())
      .then((j) => setSidos(j.items ?? [])).catch(() => {});
  }, []);

  // 공유 링크로 들어오면 설정 복원 → 입력 없이 동일 선택 결과를 바로 표시.
  //  ?s=<코드> : 서버에 저장된 짧은 코드(현행) →  base64 payload 조회
  //  ?d=<base64>: 구버전 롱링크(하위호환)
  const applyPayload = (enc: string) => {
    try {
      const json = new TextDecoder().decode(
        Uint8Array.from(atob(decodeURIComponent(enc)), (c) => c.charCodeAt(0)));
      const p = JSON.parse(json);
      if (p.inp) setInp((s) => ({ ...s, ...p.inp }));
      if (p.sido) setSido(p.sido);
      if (p.sgg) { setSgg(p.sgg); setSigungus([p.sgg]); }
      setMode("direct");
    } catch { /* 잘못된 링크는 무시 */ }
  };
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const s = q.get("s");
    if (s) {
      fetch(`${API_BASE}/buywizard/share/${encodeURIComponent(s)}`)
        .then((r) => (r.ok ? r.json() : null))
        .then((j) => { if (j?.payload) applyPayload(j.payload); })
        .catch(() => {});
      return;
    }
    const d = q.get("d");
    if (d) applyPayload(d);
  }, []);

  // 현재 설정을 base64로 인코딩(UTF-8 안전) → 서버에 저장하고 짧은 URL 반환.
  // 저장 실패 시엔 기존 롱링크(?d=)로 폴백해 공유 자체는 항상 되게 한다.
  const buildShareUrl = async (): Promise<string> => {
    const json = JSON.stringify({ inp, sido, sgg });
    const enc = btoa(String.fromCharCode(...new TextEncoder().encode(json)));
    const base = `${window.location.origin}${window.location.pathname}`;
    try {
      const r = await fetch(`${API_BASE}/buywizard/share`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ payload: enc }),
      });
      if (r.ok) { const j = await r.json(); if (j?.id) return `${base}?s=${j.id}`; }
    } catch { /* 폴백 */ }
    return `${base}?d=${encodeURIComponent(enc)}`;
  };
  const shareResult = async () => {
    const url = await buildShareUrl();
    const nav = navigator as Navigator & { share?: (d: { title?: string; url: string }) => Promise<void> };
    if (nav.share) {
      try { await nav.share({ title: "콕집 매수비용 계산 결과", url }); return; } catch { /* 취소 */ }
    }
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true); setTimeout(() => setCopied(false), 2000);
    } catch {
      window.prompt("아래 주소를 복사해 공유하세요", url);
    }
  };
  useEffect(() => {
    if (!sido) { setSggs([]); return; }
    fetch(`${API_BASE}/stats/sigungu-list?sido=${sido.slice(0, 2)}`)
      .then((r) => r.json()).then((j) => setSggs(j.items ?? [])).catch(() => {});
  }, [sido]);
  // 복원된 sgg(localStorage)가 있으면 검색 대상 목록도 복구 — 후보결과와 짝 맞춤
  useEffect(() => {
    if (sgg && sigungus.length === 0) setSigungus([sgg]);
  }, []);   // eslint-disable-line react-hooks/exhaustive-deps

  // 매수 예상지역 선택 → 규제/토허/방공제 자동판정 + 계산기 입력 자동설정 + 매물찾기 시드
  const pickRegion = (r: Region) => {
    setSgg(r);
    setSigungus([r]);
    const c = classifyRegion(sido, r.code);
    set({ loanRegion: c.loanRegion, regionalType: c.regionalType, isAdjustedArea: c.isRegulated });
  };

  const findListings = async () => {
    if (!sigungus.length) { setErr("지역(시군구)을 선택하세요"); return; }
    setErr(""); setLoading(true); setCands(null); setCandLimit(30);
    const mp = maxAffordablePrice(inp);
    setMaxP(mp);
    try {
      const r = await fetch(`${API_BASE}/buywizard/candidates`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({
          region_codes: sigungus.map((s) => s.code.slice(0, 5)),
          area_min: areaBand[0], area_max: areaBand[1], max_price: mp,
        }),
      });
      if (!r.ok) throw new Error(String(r.status));
      const j = await r.json();
      setCands(j.items ?? []);
    } catch (e) {
      setErr(`조회 실패: ${e}`);
    } finally { setLoading(false); }
  };

  // ---- 마법사 단계 (계산기 필드 채우기) ----
  const wizSelect: React.CSSProperties = {
    flex: 1, minWidth: 130, padding: "9px 10px", border: `1px solid ${BORDER}`, borderRadius: 8, fontSize: 14,
  };
  const steps: { title: string; sub?: string; icon: React.ReactNode; body: React.ReactNode; blockNext?: boolean }[] = [
    { title: "어느 지역 아파트를 보고 계신가요?", sub: "규제지역·토지거래허가구역 여부와 대출 한도가 자동 반영돼요.",
      icon: <MapPin size={30} color={PRIMARY} />, body: (
      <div style={{ display: "grid", gap: 10 }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <select value={sido} onChange={(e) => { setSido(e.target.value); setSgg(null); }} style={wizSelect}>
            <option value="">시·도</option>
            {sidos.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
          </select>
          <select value={sgg?.code ?? ""} disabled={!sido} style={wizSelect}
            onChange={(e) => { const r = sggs.find((x) => x.code === e.target.value); if (r) pickRegion(r); }}>
            <option value="">시·군·구</option>
            {sggs.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
          </select>
        </div>
        {cls && (
          <div style={{ borderRadius: 10, padding: "9px 11px", textAlign: "left",
            background: cls.regTone === "danger" ? "#fef2f2" : cls.regTone === "warn" ? "#fffbeb" : "#f0fdf4",
            border: `1px solid ${cls.regTone === "danger" ? "#fecaca" : cls.regTone === "warn" ? "#fde68a" : "#bbf7d0"}` }}>
            <div style={{ fontWeight: 800, fontSize: 13.5,
              color: cls.regTone === "danger" ? "#b91c1c" : cls.regTone === "warn" ? "#b45309" : "#15803d" }}>
              {sgg?.name} · {cls.regLabel}
            </div>
            <div style={{ fontSize: 12, color: "#475569", marginTop: 3 }}>{cls.notes[0]}</div>
          </div>
        )}
      </div>) },
    { title: "매수할 아파트의 매매가는요?", sub: "취득세·중개보수·채권까지 이 금액 기준으로 계산해요.",
      icon: <Home size={30} color={PRIMARY} />, body: (
      <MoneyField label="매매가" value={inp.salePrice} quick={Q_SALE}
        onSet={(v) => set({ salePrice: v, standardPrice: Math.floor(v * 0.7) })}
        hint="시가표준액은 매매가의 70%로 자동 추정됩니다(다음에서 수정 가능)" />) },
    { title: "주택 보유·구입 상황을 알려주세요", sub: "취득세율과 대출 한도(생애최초 우대)가 달라집니다.",
      icon: <KeyRound size={30} color={PRIMARY} />, body: (
      <>
        <div className="chip-row" style={{ marginBottom: 10 }}>
          {[0, 1, 2, 3].map((n) => (
            <button key={n} type="button" className={`chip ${inp.houseCount === n ? "active" : ""}`}
              onClick={() => set({ houseCount: n })}>
              {["무주택", "1주택", "2주택", "3주택 이상"][n]}
            </button>
          ))}
        </div>
        <div style={{ display: "grid", gap: 6, fontSize: 13.5 }}>
          <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <input type="checkbox" checked={inp.isFirstTime}
              onChange={(e) => set({ isFirstTime: e.target.checked })} />
            생애최초 구입 (취득세 감면·대출 LTV 우대)
          </label>
          <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <input type="checkbox" checked={inp.isOver85m2}
              onChange={(e) => set({ isOver85m2: e.target.checked })} />
            전용면적 85㎡ 초과 (농어촌특별세)
          </label>
          <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <input type="checkbox" checked={inp.isTempTwoHouse}
              onChange={(e) => set({ isTempTwoHouse: e.target.checked })} />
            일시적 2주택 (기존주택 처분 예정)
          </label>
          <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <input type="checkbox" checked={inp.isAdjustedArea}
              onChange={(e) => set({ isAdjustedArea: e.target.checked })} />
            조정대상지역 (2주택 8%·3주택 12% 중과)
            {cls?.isRegulated && <span className="muted" style={{ fontSize: 11.5 }}>지역 기준 자동</span>}
          </label>
        </div>
      </>) },
    { title: "대출은 얼마나 받을 예정인가요?",
      sub: reg.banned ? "이 조건은 주택담보대출이 금지됩니다"
        : cls ? `${cls.regLabel} · 최대 ${fmtEok(reg.maxLoan)}까지` : `최대 ${fmtEok(reg.maxLoan)}까지`,
      icon: <Landmark size={30} color={PRIMARY} />,
      blockNext: inp.loanAmount > reg.maxLoan,
      body: (
      <>
        {/* 생애최초는 대출 한도를 좌우 — 이 단계에서도 바로 바꿀 수 있게 */}
        <label style={{ fontSize: 13.5, display: "flex", gap: 6, alignItems: "center", marginBottom: 10,
          background: inp.isFirstTime ? "#eef4fd" : "transparent", borderRadius: 8, padding: "7px 9px" }}>
          <input type="checkbox" checked={inp.isFirstTime}
            onChange={(e) => set({ isFirstTime: e.target.checked })} />
          생애최초 구입 <span className="muted" style={{ fontSize: 12 }}>
            {inp.loanRegion === "regulated" ? "(규제지역 LTV 40%→70% 우대)" : "(LTV 우대)"}
          </span>
        </label>
        <MoneyField label="대출금(요청액)" value={inp.loanAmount} quick={Q_LOAN}
          onSet={(v) => set({ loanAmount: v })} />
        {reg.banned ? (
          <div style={{ fontSize: 12.5, marginTop: 8, color: RED, fontWeight: 600 }}>{reg.reason}</div>
        ) : (
          <div style={{ fontSize: 12.5, marginTop: 8, color: inp.loanAmount > reg.maxLoan ? RED : GREEN }}>
            {inp.loanAmount > reg.maxLoan
              ? `규제 한도를 ${fmtEok(inp.loanAmount - reg.maxLoan)} 초과했어요 — 최대 ${fmtEok(reg.maxLoan)}`
              : `규제 한도(${fmtEok(reg.maxLoan)}) 이내예요 ✓`}
          </div>
        )}
        {inp.loanAmount > reg.maxLoan && (
          <button type="button" className="chip" style={{ marginTop: 8, fontSize: 12.5 }}
            onClick={() => set({ loanAmount: reg.maxLoan })}>
            최대 한도({fmtEok(reg.maxLoan)})로 맞추기
          </button>
        )}
        <label style={{ fontSize: 13.5, display: "flex", gap: 6, alignItems: "center", marginTop: 10 }}>
          <input type="checkbox" checked={inp.hasDefenseFund}
            onChange={(e) => set({ hasDefenseFund: e.target.checked })} />
          방공제 적용 (은행이 소액임차인 보호로 대출금에서 차감)
        </label>
      </>) },
    { title: "보유 현금은 얼마인가요?", sub: "이 현금으로 살 수 있는지 계산해 드려요.",
      icon: <Wallet size={30} color={PRIMARY} />, body: (
      <MoneyField label="보유 현금" value={inp.currentCash} quick={Q_CASH}
        onSet={(v) => set({ currentCash: v })} />) },
    { title: "입주 준비 비용도 넣을까요?", sub: "이사·인테리어 예상 비용 (선택, 나중에 바꿀 수 있어요).",
      icon: <Receipt size={30} color={PRIMARY} />, body: (
      <>
        <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 2 }}>이사 비용</div>
        <div className="muted" style={{ fontSize: 11.5, marginBottom: 7, lineHeight: 1.5 }}>
          포장이사 기준 대략값이에요. 짐 양·이동거리·날짜(주말·성수기 20~30%↑)에 따라 달라집니다.
        </div>
        <div className="chip-row" style={{ marginBottom: 12 }}>
          {([["none", "없음"], ["small", "원룸·소형 100만"], ["medium", "20~30평대 150만"], ["large", "대형 200만"]] as const).map(([k, l]) => (
            <button key={k} type="button" className={`chip ${inp.movingFeePreset === k ? "active" : ""}`}
              onClick={() => set({ movingFeePreset: k })}>{l}</button>
          ))}
        </div>
        <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 2 }}>인테리어</div>
        <div className="muted" style={{ fontSize: 11.5, marginBottom: 7, lineHeight: 1.5 }}>
          매매가 대비 비율로 잡은 대략값이에요. 부분수리(3%)·주방/욕실 포함 표준(5%)·전체 올수리(8%).
        </div>
        <div className="chip-row">
          {([["none", "없음", 0], ["basic", "부분 3%", 0.03], ["standard", "표준 5%", 0.05], ["premium", "올수리 8%", 0.08]] as const).map(([k, l, r]) => (
            <button key={k} type="button" className={`chip ${inp.interiorFeePreset === k ? "active" : ""}`}
              onClick={() => set({ interiorFeePreset: k })}>
              {l}{r > 0 ? ` · ${fmtEok(Math.floor(inp.salePrice * r))}` : ""}
            </button>
          ))}
        </div>
      </>) },
  ];

  return (
    <div className="page" style={{ maxWidth: 880 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", margin: "0 0 2px" }}>
        <h1 style={{ margin: 0 }}>아파트매수계산기</h1>
        <button type="button" className="chip" style={{ marginLeft: "auto" }}
          onClick={() => { setInp(DEFAULT_INPUT); setCands(null); }}>
          <RotateCcw size={12} style={{ verticalAlign: -1.5 }} /> 초기화
        </button>
      </div>
      <div className="muted" style={{ marginBottom: 14 }}>
        계약금·취득세·중개보수·채권·등기비까지 실제 발생 비용 전부 계산하고,
        그 예산으로 <b>실제 살 수 있는 단지</b>까지 찾아드립니다.
      </div>

      {mode === "ask" && (
        <div className="modal-overlay">
          <div className="modal-card" style={{ maxWidth: 400, textAlign: "center" }}>
            <Wand2 size={34} color={PRIMARY} style={{ margin: "6px auto 10px" }} />
            <div style={{ fontSize: 17, fontWeight: 800, marginBottom: 6 }}>
              입력이 많아요. 마법사로 진행할까요?
            </div>
            <div className="muted" style={{ fontSize: 13, marginBottom: 16 }}>
              {steps.length}개 질문에 하나씩 답하면 자동으로 채워드립니다.<br />
              익숙하시면 한 페이지에서 직접 입력할 수도 있어요.
            </div>
            <div style={{ display: "grid", gap: 8 }}>
              <button type="button" style={{ ...PBTN, padding: "11px 0", fontSize: 15 }}
                onClick={() => { setMode("wizard"); setStep(0); }}>
                <Wand2 size={15} style={{ verticalAlign: -2, marginRight: 5 }} />마법사로 시작
              </button>
              <button type="button"
                style={{ width: "100%", padding: "11px 0", fontSize: 14, textAlign: "center",
                  background: "#fff", color: "#334155", border: `1px solid ${BORDER}`,
                  borderRadius: 10, fontWeight: 700, cursor: "pointer" }}
                onClick={() => setMode("direct")}>
                <Calculator size={14} style={{ verticalAlign: -2, marginRight: 5 }} />직접 입력할게요
              </button>
            </div>
          </div>
        </div>
      )}

      {mode === "wizard" && (
        <div className="modal-overlay">
          <div className="modal-card" style={{ maxWidth: 470 }}>
            <div className="modal-head">
              <span className="modal-title">단계 {step + 1} / {steps.length}</span>
              <button className="phone-banner-x" aria-label="닫기" onClick={() => setMode("direct")}><X size={16} /></button>
            </div>
            <div style={{ height: 4, background: "#eef2f7", borderRadius: 99, margin: "4px 0 14px" }}>
              <div style={{ height: 4, width: `${((step + 1) / steps.length) * 100}%`, background: PRIMARY, borderRadius: 99 }} />
            </div>
            <div style={{ textAlign: "center", marginBottom: 14 }}>
              <div style={{ width: 60, height: 60, borderRadius: 16, background: "#eef4fd",
                display: "inline-flex", alignItems: "center", justifyContent: "center", marginBottom: 8 }}>
                {steps[step].icon}
              </div>
              <div style={{ fontSize: 16.5, fontWeight: 800 }}>{steps[step].title}</div>
              {steps[step].sub && (
                <div className="muted" style={{ fontSize: 12.5, marginTop: 3 }}>{steps[step].sub}</div>
              )}
            </div>
            <div style={{ minHeight: 110 }}>{steps[step].body}</div>
            {steps[step].blockNext && (
              <div style={{ fontSize: 12, color: RED, textAlign: "right", marginTop: 8 }}>
                대출 한도를 초과했어요. 금액을 줄이거나 위 ‘한도로 맞추기’를 눌러주세요.
              </div>
            )}
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 12 }}>
              <button type="button" className="chip" disabled={step === 0}
                onClick={() => setStep((s) => Math.max(0, s - 1))}>
                <ChevronLeft size={14} style={{ verticalAlign: -2 }} />이전
              </button>
              {step < steps.length - 1 ? (
                <button type="button" disabled={steps[step].blockNext}
                  style={{ ...PBTN, padding: "8px 18px", opacity: steps[step].blockNext ? 0.5 : 1,
                    cursor: steps[step].blockNext ? "not-allowed" : "pointer" }}
                  onClick={() => { if (!steps[step].blockNext) setStep((s) => s + 1); }}>
                  다음<ChevronRight size={14} style={{ verticalAlign: -2 }} />
                </button>
              ) : (
                <button type="button" style={{ ...PBTN, padding: "8px 18px" }}
                  onClick={() => setMode("direct")}>
                  결과 보기
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ================= 매수 예상지역 (가장 먼저) ================= */}
      <div style={{ ...CARD, marginBottom: 12 }}>
        <SecTitle step={1}>매수 예상지역</SecTitle>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <select value={sido} onChange={(e) => { setSido(e.target.value); setSgg(null); }}
            style={{ flex: 1, minWidth: 130, padding: "9px 10px", border: `1px solid ${BORDER}`, borderRadius: 8, fontSize: 14 }}>
            <option value="">시·도 선택</option>
            {sidos.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
          </select>
          <select value={sgg?.code ?? ""} disabled={!sido}
            onChange={(e) => { const r = sggs.find((x) => x.code === e.target.value); if (r) pickRegion(r); }}
            style={{ flex: 1, minWidth: 130, padding: "9px 10px", border: `1px solid ${BORDER}`, borderRadius: 8, fontSize: 14 }}>
            <option value="">시·군·구 선택</option>
            {sggs.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
          </select>
        </div>
        {cls ? (
          <div style={{ marginTop: 10, borderRadius: 10, padding: "10px 12px",
            background: cls.regTone === "danger" ? "#fef2f2" : cls.regTone === "warn" ? "#fffbeb" : "#f0fdf4",
            border: `1px solid ${cls.regTone === "danger" ? "#fecaca" : cls.regTone === "warn" ? "#fde68a" : "#bbf7d0"}` }}>
            <div style={{ fontWeight: 800, fontSize: 14,
              color: cls.regTone === "danger" ? "#b91c1c" : cls.regTone === "warn" ? "#b45309" : "#15803d" }}>
              {sgg?.name} · {cls.regLabel}
            </div>
            <ul style={{ margin: "6px 0 0", paddingLeft: 16, fontSize: 12, color: "#475569" }}>
              {cls.notes.map((n, i) => <li key={i} style={{ marginBottom: 2 }}>{n}</li>)}
            </ul>
            <div className="muted" style={{ fontSize: 11.5, marginTop: 5 }}>
              선택에 따라 대출규제·방공제·조정대상지역이 자동 설정됩니다 (아래에서 수정 가능).
            </div>
          </div>
        ) : (
          <div className="muted" style={{ fontSize: 12.5, marginTop: 8 }}>
            매수하려는 지역을 먼저 선택하면 규제지역·토지거래허가구역 여부와 대출 한도가 자동 반영됩니다.
          </div>
        )}
      </div>

      {/* ================= 기본 정보 ================= */}
      <div style={{ ...CARD, marginBottom: 12 }}>
        <SecTitle step={2}>기본 정보 <span style={{ fontSize: 12, fontWeight: 500, color: "#94a3b8", marginLeft: 4 }}>매매가·대출·현금</span></SecTitle>
        <div style={{ display: "grid", gap: 16 }}>
          {/* 매매가 · 대출금 — 가로 배열 */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16 }}>
            <MoneyField label="매매가" value={inp.salePrice} quick={Q_SALE}
              onSet={(v) => set({ salePrice: v })} />
            <MoneyField label="대출금 (요청액)" value={inp.loanAmount} quick={Q_LOAN}
              onSet={(v) => set({ loanAmount: v })} />
          </div>
          <div className="muted" style={{ fontSize: 11.5, marginTop: -8 }}>
            * 인지세는 대출금액 기준 자동 계산 (1천만~5천만: 5만 · ~1억: 10만 · 1억 초과: 15만)
          </div>

          {/* 정부 대출규제 한도 체크 — 지역·가격·주택상황에 따라 대출 가능액이 달라짐 */}
          <div>
            <div style={{ border: `1px solid ${loanOver || reg.banned ? "#f4c7c7" : BORDER}`,
              background: loanOver || reg.banned ? "#fef7f7" : "#f8fafc", borderRadius: 10, padding: "10px 12px" }}>
              <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 6 }}>
                <Landmark size={14} style={{ verticalAlign: -2, marginRight: 4 }} />정부 대출규제 한도
                <Hint text={"현행 기준(2025.10.15 대책 + 2026.6.30 추가지정).\n• 규제지역 = 서울 25개구 전역 + 경기 15곳\n  - 10.15: 과천·광명·하남·의왕·수원 영통/장안/팔달·성남 분당/수정/중원·안양 동안·용인 수지\n  - 2026.6.30 추가(규제 7.1·토허 7.5 효력): 화성 동탄구·용인 기흥구·구리시\n• 규제지역 전체가 토지거래허가구역(2년 실거주·갭투자 불가)\n• 수도권·규제지역: 다주택/1주택(유지) 추가구입 주담대 금지\n• 규제지역 LTV 40%(생애최초 예외 70%), 수도권 비규제 70%, 지방 70%(생애최초 80%)\n• 규제지역 캡(가격대별): 15억↓ 6억 / 15~25억 4억 / 25억↑ 2억 — 생애최초도 이 캡은 동일(LTV만 70% 우대). 수도권 비규제 6억 정액\n예) 서울 20억 생애최초: LTV 70%는 14억이지만 15~25억 캡 4억에 막혀 최대 4억\n실제 한도는 DSR·소득·은행 심사로 더 줄 수 있습니다."} />
              </div>
              <div className="chip-row" style={{ marginBottom: 8 }}>
                {([["regulated", "규제지역 (서울 전역·경기 12곳)"], ["capital", "수도권 비규제"], ["other", "그 외 지방"]] as const).map(([k, l]) => (
                  <button key={k} type="button" className={`chip ${inp.loanRegion === k ? "active" : ""}`}
                    onClick={() => set({ loanRegion: k })}>{l}</button>
                ))}
              </div>
              {reg.banned ? (
                <div style={{ fontSize: 13, color: RED, fontWeight: 600 }}>{reg.reason}</div>
              ) : (
                <>
                  <div style={{ display: "grid", gap: 3, fontSize: 12.5, color: "#475569" }}>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span>LTV {Math.round(reg.ltv * 100)}% ({reg.buyerLabel}{inp.isFirstTime && inp.houseCount === 0 ? "·생애최초" : ""})</span>
                      <b>{fmtEok(reg.ltvAmt)}</b>
                    </div>
                    {reg.cap != null && (
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <span>가격별 주담대 캡 (매매가 {fmtEok(inp.salePrice)})</span>
                        <b>{fmtEok(reg.cap)}</b>
                      </div>
                    )}
                    <div style={{ display: "flex", justifyContent: "space-between", borderTop: `1px solid ${BORDER}`, paddingTop: 4, marginTop: 2 }}>
                      <span style={{ fontWeight: 700, color: "#0f172a" }}>최대 대출 가능액</span>
                      <b style={{ color: PRIMARY, fontSize: 13.5 }}>{fmtEok(reg.maxLoan)}</b>
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8, flexWrap: "wrap" }}>
                    {loanOver ? (
                      <span style={{ fontSize: 12.5, color: RED, fontWeight: 600 }}>
                        입력 대출금이 규제 한도를 {fmtEok(inp.loanAmount - reg.maxLoan)} 초과합니다
                      </span>
                    ) : (
                      <span style={{ fontSize: 12.5, color: GREEN }}>입력 대출금 {fmtEok(inp.loanAmount)} — 한도 이내</span>
                    )}
                    {inp.loanAmount !== reg.maxLoan && (
                      <button type="button" className="chip" style={{ fontSize: 12 }}
                        onClick={() => set({ loanAmount: reg.maxLoan })}>
                        한도({fmtEok(reg.maxLoan)})를 대출금에 적용
                      </button>
                    )}
                  </div>
                </>
              )}
            </div>
            <label style={{ fontSize: 13.5, display: "flex", gap: 6, alignItems: "center", marginTop: 8 }}>
              <input type="checkbox" checked={inp.hasDefenseFund}
                onChange={(e) => set({ hasDefenseFund: e.target.checked })} />
              방공제 적용
              <Hint text={"방공제는 은행이 소액임차인(세입자) 보증금 보호를 위해 대출금에서 미리 차감하는 금액입니다.\n체크 해제 시 대출금 전액 수령 가정."} />
            </label>
            {inp.hasDefenseFund && (
              <div style={{ margin: "8px 0 0 22px", display: "grid", gap: 6 }}>
                {inp.manualDefenseFund != null ? (
                  <div>
                    <div style={{ fontSize: 12.5, color: "#64748b", marginBottom: 4 }}>
                      방공제 금액 직접 입력
                      <button type="button" onClick={() => set({ manualDefenseFund: null })}
                        style={{ marginLeft: 8, background: "none", border: "none", color: PRIMARY,
                          fontSize: 11.5, fontWeight: 600, cursor: "pointer" }}>지역 기준 자동으로</button>
                    </div>
                    <MoneyField label="" value={inp.manualDefenseFund} quick={[]}
                      onSet={(v) => set({ manualDefenseFund: v })} />
                  </div>
                ) : sgg ? (
                  <div style={{ fontSize: 12.5, color: "#334155", background: "#f1f5f9",
                    borderRadius: 8, padding: "8px 10px" }}>
                    지역 기준 자동: <b>{RT_LABEL[inp.regionalType]}</b> — 대출금에서{" "}
                    <b>{fmtWon(defenseFundAmount(inp.regionalType))}</b> 차감
                    <button type="button" onClick={() => set({ manualDefenseFund: defenseFundAmount(inp.regionalType) })}
                      style={{ marginLeft: 8, background: "none", border: "none", color: PRIMARY,
                        fontSize: 11.5, fontWeight: 600, cursor: "pointer" }}>직접 입력</button>
                    <span className="muted" style={{ fontSize: 11.5, display: "block", marginTop: 2 }}>
                      매수 예상지역에 따라 자동 설정됩니다.
                    </span>
                  </div>
                ) : (
                  <>
                    <div style={{ fontSize: 12.5, color: "#64748b" }}>
                      지역 구분 (방공제 금액 기준)
                      <button type="button" onClick={() => set({ manualDefenseFund: defenseFundAmount(inp.regionalType) })}
                        style={{ marginLeft: 8, background: "none", border: "none", color: PRIMARY,
                          fontSize: 11.5, fontWeight: 600, cursor: "pointer" }}>직접 입력</button>
                    </div>
                    <div style={{ display: "grid", gap: 4, fontSize: 13 }}>
                      {([["seoul", "서울 (5,500만원)"], ["overconcentration", "과밀억제권역 (5,000만원)"],
                        ["metro", "광역시 (2,800만원)"], ["other", "기타 지방 (2,000만원)"]] as const).map(([k, l]) => (
                        <label key={k} style={{ display: "flex", gap: 6, alignItems: "center" }}>
                          <input type="radio" name="regionalType" checked={inp.regionalType === k}
                            onChange={() => set({ regionalType: k, manualDefenseFund: null })} /> {l}
                        </label>
                      ))}
                    </div>
                  </>
                )}
                <div style={{ fontSize: 13, color: "#334155" }}>
                  실제 대출 가능 금액: <b>{fmtWon(res.actualLoan)}</b>
                  <span className="muted" style={{ fontSize: 12 }}>
                    {" "}(대출금 {fmtWon(inp.loanAmount)} - 방공제 {fmtWon(res.defenseFund)})
                  </span>
                </div>
              </div>
            )}
          </div>
          {/* 보유 현금 · 계약금 비율 — 가로 배열 */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16 }}>
            <MoneyField label="보유 현금" value={inp.currentCash} quick={Q_CASH}
              onSet={(v) => set({ currentCash: v })} />
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 4 }}>
                계약금 비율 <Hint text="계약 시 지불할 계약금 비율입니다. 보통 10% 정도입니다." />
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <input type="text" inputMode="decimal" value={String(inp.downPaymentRatio)}
                  onChange={(e) => set({ downPaymentRatio: parseFloat(e.target.value.replace(/[^\d.]/g, "")) || 0 })}
                  style={{ width: 80, padding: "8px 10px", border: `1px solid ${BORDER}`, borderRadius: 8, fontSize: 14, textAlign: "right" }} />
                <span style={{ fontSize: 14, fontWeight: 600 }}>%</span>
                <span className="muted" style={{ fontSize: 13 }}>계약금 {fmtWon(res.downPayment)}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ================= 취득세 계산 조건 ================= */}
      <div style={{ ...CARD, marginBottom: 12 }}>
        <SecTitle step={3}>취득세 계산 조건</SecTitle>
        <div style={{ display: "grid", gap: 8, fontSize: 13.5 }}>
          <div>
            <div style={{ fontSize: 12.5, color: "#64748b", marginBottom: 5 }}>
              주택 수 (구입 전 기준)
              <Hint text={"현재 보유 주택 수에 따라 취득세율이 달라집니다.\n• 1주택 이하: 누진세율\n• 2주택: 비조정 1% / 조정 8%\n• 3주택 이상: 비조정 3% / 조정 12%"} />
            </div>
            <div className="chip-row">
              {[0, 1, 2, 3].map((n) => (
                <button key={n} type="button" className={`chip ${inp.houseCount === n ? "active" : ""}`}
                  onClick={() => set({ houseCount: n })}>
                  {["무주택", "1주택", "2주택", "3주택 이상"][n]}
                </button>
              ))}
            </div>
          </div>
          <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <input type="checkbox" checked={inp.isAdjustedArea}
              onChange={(e) => set({ isAdjustedArea: e.target.checked })} />
            조정대상지역
            <Hint text={"조정대상지역 여부에 따라 취득세율이 달라집니다.\n• 2주택: 비조정 1% → 조정 8%\n• 3주택: 비조정 3% → 조정 12%"} />
          </label>
          <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <input type="checkbox" checked={inp.isOver85m2}
              onChange={(e) => set({ isOver85m2: e.target.checked })} />
            전용면적 85㎡ 초과
            <Hint text={"85㎡ 이하 + 1주택 이하 + 6억 이하면 농어촌특별세가 면제됩니다.\n85㎡ 초과 시 취득세의 10%가 부과됩니다."} />
          </label>
          <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <input type="checkbox" checked={inp.isFirstTime}
              onChange={(e) => set({ isFirstTime: e.target.checked })} />
            생애최초
            <Hint text={"생애최초 구입 시 취득세 감면 (6억·85㎡ 이하 조건, 최대 200만원 수준)이 자동 반영됩니다."} />
          </label>
          <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <input type="checkbox" checked={inp.isTempTwoHouse}
              onChange={(e) => set({ isTempTwoHouse: e.target.checked })} />
            일시적 2주택
            <Hint text="이사 등으로 일시적 2주택이 되는 경우(기존주택 처분 예정) 1주택 세율(구간식)을 적용합니다." />
          </label>
          <div>
            <div style={{ fontSize: 12.5, color: "#64748b", marginBottom: 4 }}>
              시가표준액
              <Hint text={"지방세 계산 기준 금액(공시가격 계열). 등록면허세·국민주택채권 계산에 사용됩니다.\n부동산공시가격 알리미·위택스에서 조회하세요. 모르면 매매가의 60~70%로 임시 추정."} />
            </div>
            <MoneyField label="" value={inp.standardPrice} quick={[]}
              onSet={(v) => set({ standardPrice: v })} />
            <button type="button" className="chip" style={{ marginTop: 4, fontSize: 12 }}
              onClick={() => set({ standardPrice: Math.floor(inp.salePrice * 0.7) })}>
              매매가의 70%로 추정
            </button>
          </div>
        </div>
      </div>

      {/* ================= 실무 비용 (접이식) ================= */}
      <Collapsible title="실무 비용 (선택사항)">
        <div style={{ display: "grid", gap: 14, fontSize: 13.5 }}>
          <PresetRow label={`중개보수 — 자동: ${fmtWon(brokerageFee(inp.salePrice))}`}
            options={[["auto", "자동 계산"], ["manual", "직접 입력"]]}
            value={inp.brokerageFeePreset}
            onSelect={(v) => set({ brokerageFeePreset: v as CalcInput["brokerageFeePreset"] })} />
          {inp.brokerageFeePreset === "manual" && (
            <MoneyField label="중개보수 직접 입력" value={inp.manualBrokerageFee} quick={[]}
              onSet={(v) => set({ manualBrokerageFee: v })} />
          )}
          <PresetRow label={`법무사 비용 — 자동: ${fmtWon(lawyerFee(inp.salePrice))}`}
            options={[["auto", "자동 계산"], ["manual", "직접 입력"]]}
            value={inp.lawyerFeePreset}
            onSelect={(v) => set({ lawyerFeePreset: v as CalcInput["lawyerFeePreset"],
              ...(v === "manual" && !inp.manualLawyerFee ? { manualLawyerFee: lawyerFee(inp.salePrice) } : {}) })} />
          {inp.lawyerFeePreset === "manual" && (
            <>
              <MoneyField label="법무사 비용 직접 입력" value={inp.manualLawyerFee} quick={[]}
                onSet={(v) => set({ manualLawyerFee: v })} />
              <SetChips value={inp.manualLawyerFee} onSet={(v) => set({ manualLawyerFee: v })}
                amounts={[[0, "셀프등기 0원"], [5e5, "50만"], [7e5, "70만"], [1e6, "100만"], [15e5, "150만"]]} />
            </>
          )}
          <GuideBox title="법무사 비용 가이드" rows={[
            ["매매가 1억 이하", "40만 ~ 60만원"],
            ["1억 ~ 3억", "60만 ~ 80만원"],
            ["3억 ~ 5억", "80만 ~ 120만원"],
            ["5억 ~ 10억", "100만 ~ 150만원"],
            ["10억 ~ 20억", "130만 ~ 200만원 내외"],
          ]} note="소유권이전등기 기본보수에 부가세·제증명·일당·교통비·취득세 신고 대행·국민주택채권 매입 대행 등 부대비가 더해집니다. 권리관계·대출·근저당 설정 여부, 법무사별 청구 방식에 따라 차이가 큽니다. 셀프등기 시 보수는 줄지만 취득세·인지세·등기신청수수료·국민주택채권 등 공과금은 동일하게 발생합니다." />
          <MoneyField label="선수관리비 (세대마다 다름)" value={inp.managementDeposit}
            quick={Q_MGMT} onSet={(v) => set({ managementDeposit: v })}
            hint="입주 시 관리사무소에 미리 내는 관리비 예치금입니다. 단지가 아니라 세대(면적)마다 다릅니다." />
          <PresetRow label="청소 비용"
            options={[["none", "없음"], ["basic", "기본 (20만원)"], ["premium", "프리미엄 (50만원)"], ["manual", "직접 입력"]]}
            value={inp.cleaningFeePreset}
            onSelect={(v) => set({ cleaningFeePreset: v as CalcInput["cleaningFeePreset"] })} />
          {inp.cleaningFeePreset === "manual" && (
            <MoneyField label="청소 비용 직접 입력" value={inp.manualCleaningFee} quick={[]}
              onSet={(v) => set({ manualCleaningFee: v })} />
          )}
          <PresetRow label="이사 비용"
            options={[["none", "없음"], ["small", "100만원"], ["medium", "150만원"], ["large", "200만원"], ["manual", "직접 입력"]]}
            value={inp.movingFeePreset}
            onSelect={(v) => set({ movingFeePreset: v as CalcInput["movingFeePreset"],
              ...(v === "manual" && !inp.manualMovingFee ? { manualMovingFee: 15e5 } : {}) })} />
          {inp.movingFeePreset === "manual" && (
            <>
              <MoneyField label="이사 비용 직접 입력" value={inp.manualMovingFee} quick={[]}
                onSet={(v) => set({ manualMovingFee: v })} />
              <SetChips value={inp.manualMovingFee} onSet={(v) => set({ manualMovingFee: v })}
                amounts={[[5e5, "50만"], [1e6, "100만"], [15e5, "150만"], [2e6, "200만"], [25e5, "250만"]]} />
            </>
          )}
          <GuideBox title="이사 비용 가이드 (포장이사 기준)" rows={[
            ["원룸·소형", "30만 ~ 70만원"],
            ["소형 아파트·오피스텔", "60만 ~ 100만원"],
            ["20평대 (59㎡ 전후)", "90만 ~ 150만원"],
            ["30평대 (84㎡ 전후)", "130만 ~ 220만원"],
            ["40평대 이상", "200만 ~ 300만원 이상"],
          ]} note="평형보다 실제 짐 양·차량 톤수·인원·이동거리·사다리차·날짜에 따라 달라집니다. 사다리차, 에어컨 이전 설치, 붙박이장·시스템가구 분해·재설치, 피아노·대형가전 운반, 입주청소, 엘리베이터 사용료 등은 별도입니다. 손 없는 날·주말·월말, 2~4월·9~10월 성수기에는 20~30% 높아질 수 있으니 최소 2~3곳 견적 비교를 권장합니다." />
          <PresetRow label="인테리어 비용"
            options={[["none", "없음"], ["basic", "기본 (매매가 3%)"], ["standard", "표준 (매매가 5%)"], ["premium", "프리미엄 (매매가 8%)"], ["manual", "직접 입력"]]}
            value={inp.interiorFeePreset}
            onSelect={(v) => set({ interiorFeePreset: v as CalcInput["interiorFeePreset"] })} />
          {inp.interiorFeePreset !== "none" && inp.interiorFeePreset !== "manual" && (
            <div style={{ fontSize: 13, color: "#334155", marginTop: -4 }}>
              인테리어 예상: <b style={{ color: PRIMARY }}>
                {fmtWon(Math.floor(inp.salePrice * (INTERIOR[inp.interiorFeePreset] as number)))}</b>
              <span className="muted" style={{ fontSize: 12 }}>
                {" "}(매매가 {Math.round((INTERIOR[inp.interiorFeePreset] as number) * 100)}%)
              </span>
            </div>
          )}
          {inp.interiorFeePreset === "manual" && (
            <MoneyField label="인테리어 직접 입력" value={inp.manualInteriorFee} quick={[]}
              onSet={(v) => set({ manualInteriorFee: v })} />
          )}
          {/* 예비비 — 부대비용 합계 기준 여유분 */}
          <div style={{ borderTop: `1px solid ${BORDER}`, paddingTop: 12 }}>
            <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 4 }}>
              예비비 비율
              <Hint text={"세금·수수료 외에 예상치 못한 비용에 대비한 여유분입니다.\n부대비용 합계에 이 비율만큼 더해 계산합니다. 보통 10% 정도."} />
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <input type="text" inputMode="decimal" value={String(inp.contingencyRatio)}
                onChange={(e) => set({ contingencyRatio: parseFloat(e.target.value.replace(/[^\d.]/g, "")) || 0 })}
                style={{ width: 80, padding: "8px 10px", border: `1px solid ${BORDER}`, borderRadius: 8, fontSize: 14, textAlign: "right" }} />
              <span style={{ fontSize: 14, fontWeight: 600 }}>%</span>
              <span className="muted" style={{ fontSize: 13 }}>
                예비비 {fmtWon(res.items.find((x) => x.id === "contingency")?.amount ?? 0)}
              </span>
            </div>
          </div>
        </div>
      </Collapsible>

      {/* ================= 결과: 최종 보유현금 ================= */}
      <div style={{ ...CARD, borderColor: ok ? GREEN : RED, borderWidth: 1.5, marginBottom: 12, overflow: "hidden", position: "relative" }}>
        <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 4, background: ok ? GREEN : RED }} />
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 4 }}>
          <span style={{ fontSize: 11.5, fontWeight: 700, letterSpacing: 2, color: "#8296ab" }}>최종 보유현금</span>
          <span className="txf-b" style={{ background: ok ? "#eefaf2" : "#fef2f2", color: ok ? GREEN : RED }}>
            {ok ? "충분" : "부족"}
          </span>
        </div>
        <div style={{ fontSize: 30, fontWeight: 800, color: ok ? GREEN : RED, margin: "4px 0 2px" }}>
          {ok ? "+" : "-"}{fmtEok(Math.abs(res.cashGap))}
          <span style={{ fontSize: 16, marginLeft: 4 }}>원</span>
        </div>
        {/* 보유/필요 진행바 */}
        <div style={{ height: 8, background: "#eef2f7", borderRadius: 99, margin: "10px 0 6px" }}>
          <div style={{ height: 8, borderRadius: 99, background: ok ? GREEN : RED,
            width: `${Math.min(res.minRequiredCash > 0 ? (res.actualCash / res.minRequiredCash) * 100 : 100, 100)}%` }} />
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
          <span>보유현금 <b>{fmtEok(res.actualCash)}</b></span>
          <span>필요현금 <b>{fmtEok(res.minRequiredCash)}</b></span>
        </div>
        {!ok && (
          <div style={{ fontSize: 12.5, color: RED, marginTop: 6 }}>
            부족액 {fmtEok(-res.cashGap)} · 추가 자금 마련이나 대출 증액을 고려하세요
          </div>
        )}
        <div style={{ display: "grid", gap: 6, marginTop: 12, fontSize: 13.5 }}>
          <RowKV k="최소 필요현금" v={fmtWon(res.minRequiredCash)} sub="대출 제외, 실제 필요한 현금" strong />
          <RowKV k="총 필요자기자본" v={fmtWon(res.totalWithLoan)} sub="대출금 포함 전체 필요 자금" />
        </div>
        <button type="button" onClick={shareResult}
          style={{ width: "100%", marginTop: 14, padding: "12px 0", fontSize: 14.5, fontWeight: 700,
            background: PRIMARY, color: "#fff", border: "none", borderRadius: 10, cursor: "pointer",
            display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 6 }}>
          <Share2 size={16} /> {copied ? "링크가 복사됐어요!" : "결과 공유하기"}
        </button>
        <div className="muted" style={{ fontSize: 11.5, textAlign: "center", marginTop: 6 }}>
          입력한 조건이 링크에 담겨요. 받은 사람이 링크를 열면 같은 결과가 그대로 보입니다.
          {copied && <span style={{ color: GREEN, display: "block" }}>카카오톡·문자에 붙여넣어 보내세요.</span>}
        </div>
      </div>

      {/* ================= 자금 구성 한눈에 보기 ================= */}
      <div style={{ ...CARD, marginBottom: 12 }}>
        <SecTitle>자금 구성 한눈에 보기</SecTitle>
        <div style={{ display: "grid", gap: 12, fontSize: 13.5 }}>
          <div>
            <b style={{ display: "inline-flex", alignItems: "center", gap: 5 }}><Wallet size={15} />매매가 구성</b>
            <RowKV k="계약금" v={fmtWon(res.downPayment)} indent />
            <RowKV k="+ 잔금 (현금 필요)" v={fmtWon(res.balancePayment)} indent />
            <RowKV k="+ 대출 (실수령)" v={fmtWon(res.actualLoan)} indent />
            <RowKV k="= 매매가" v={fmtWon(inp.salePrice)} indent strong />
          </div>
          {inp.hasDefenseFund && (
            <div>
              <b style={{ display: "inline-flex", alignItems: "center", gap: 5 }}><Landmark size={15} />대출금 구성</b>
              <RowKV k="대출 승인액" v={fmtWon(inp.loanAmount)} indent />
              <RowKV k="- 방공제 (은행 차감)" v={fmtWon(res.defenseFund)} indent />
              <RowKV k="= 실제 받는 금액" v={fmtWon(res.actualLoan)} indent strong />
            </div>
          )}
          <div>
            <b style={{ display: "inline-flex", alignItems: "center", gap: 5 }}><Receipt size={15} />부대비용 요약</b>
            <RowKV k="세금 합계 (취득세·교육세·농특세·등록면허세)" v={fmtWon(res.taxTotal)} indent />
            <RowKV k="실비용 등 합계 (중개보수·채권·법무·이사…)" v={fmtWon(res.extraTotal - res.taxTotal)} indent />
            <RowKV k="= 부대비용 총액" v={fmtWon(res.extraTotal)} indent strong />
          </div>
        </div>
      </div>

      {/* ================= 순서 흐름도 ================= */}
      <div style={{ ...CARD, marginBottom: 12 }}>
        <SecTitle>순서 흐름도</SecTitle>
        <div style={{ display: "grid", gap: 0 }}>
          {STAGE_ORDER.map((st, idx) => {
            const items = res.items.filter((x) => x.stage === st);
            const sum = items.reduce((s, x) => s + x.amount, 0);
            if (!items.length) return null;
            return (
              <div key={st} style={{ display: "flex", gap: 10, alignItems: "stretch" }}>
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
                  <div style={{ width: 22, height: 22, borderRadius: 99, background: PRIMARY, color: "#fff",
                    fontSize: 11.5, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center" }}>
                    {idx + 1}
                  </div>
                  <div style={{ flex: 1, width: 2, background: "#e2e8f0" }} />
                </div>
                <div style={{ paddingBottom: 14, flex: 1 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 14 }}>
                    <b>{STAGE_LABEL[st]}</b>
                    <b style={{ color: PRIMARY }}>{fmtWon(sum)}</b>
                  </div>
                  {items.map((x) => (
                    <div key={x.id} style={{ display: "flex", justifyContent: "space-between", fontSize: 12.5, color: "#64748b", marginTop: 2 }}>
                      <span>{x.label}{x.formula ? ` — ${x.formula}` : x.note ? ` — ${x.note}` : ""}</span>
                      <span style={{ fontVariantNumeric: "tabular-nums" }}>{fmtWon(x.amount)}</span>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 14, borderTop: `1px solid ${BORDER}`, paddingTop: 8 }}>
            <b>전체 합계 (최소 필요현금)</b><b>{fmtWon(res.minRequiredCash)}</b>
          </div>
        </div>
      </div>

      {/* ================= 콕집 차별화: 살 수 있는 단지 찾기 ================= */}
      <div style={{ ...CARD, marginBottom: 20, background: "#f6faff" }}>
        <SecTitle><MapPin size={15} color={PRIMARY} style={{ verticalAlign: -2, marginRight: 4 }} />
          이 조건으로 살 수 있는 단지 찾기</SecTitle>
        <div className="muted" style={{ fontSize: 12.5, marginBottom: 10 }}>
          현재 대출금·현금 기준으로 잔금까지 가능한 <b>최대 매매가</b>를 역산해,
          콕집 실거래·매물 DB에서 실제 매물을 찾아드립니다.
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 8 }}>
          <select value={sido} onChange={(e) => setSido(e.target.value)}
            style={{ padding: "8px 10px", border: `1px solid ${BORDER}`, borderRadius: 8, fontSize: 14 }}>
            <option value="">시·도 선택</option>
            {sidos.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
          </select>
          <select value="" disabled={!sido}
            onChange={(e) => {
              const r = sggs.find((s) => s.code === e.target.value);
              if (r && !sigungus.some((s) => s.code === r.code)) setSigungus([...sigungus, r]);
            }}
            style={{ padding: "8px 10px", border: `1px solid ${BORDER}`, borderRadius: 8, fontSize: 14 }}>
            <option value="">시·군·구 추가</option>
            {sggs.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
          </select>
          {([[0, 59, "~59㎡"], [59, 85, "59~85㎡"], [85, 115, "85~115㎡"], [115, 300, "115㎡~"]] as const).map(([a, b, l]) => (
            <button key={l} type="button" className={`chip ${areaBand[0] === a && areaBand[1] === b ? "active" : ""}`}
              onClick={() => setAreaBand([a, b])}>{l}</button>
          ))}
        </div>
        {sigungus.length > 0 && (
          <div className="chip-row" style={{ marginBottom: 8 }}>
            {sigungus.map((s) => (
              <span key={s.code} className="chip active" style={{ display: "inline-flex", gap: 4, alignItems: "center" }}>
                {s.name}
                <X size={12} style={{ cursor: "pointer" }}
                  onClick={() => setSigungus(sigungus.filter((x) => x.code !== s.code))} />
              </span>
            ))}
          </div>
        )}
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <button type="button"
            style={{ ...PBTN, width: "100%", display: "flex", alignItems: "center",
                     justifyContent: "center", padding: "15px 24px",
                     fontSize: 16.5, fontWeight: 700, borderRadius: 12, gap: 8 }}
            disabled={loading} onClick={findListings}>
            {loading ? <Loader2 size={18} style={SPIN} /> : <Building2 size={18} style={{ verticalAlign: -3 }} />}
            {" "}이 조건으로 매매 가능 단지 찾기
          </button>
          {err && <span style={{ color: RED, fontSize: 13 }}>{err}</span>}
        </div>

        {cands && (
          <div style={{ marginTop: 14 }}>
            <div style={{ fontSize: 14, marginBottom: 8 }}>
              구매 가능 최대 매매가 <b style={{ color: PRIMARY, fontSize: 16 }}>{fmtEok(maxP)}</b>
              <span className="muted" style={{ fontSize: 12 }}> — 이하 매물 {cands.length}건{cands.length >= 600 ? "+" : ""}
                {cands.length > candLimit ? ` (${Math.min(candLimit, cands.length)}건 표시)` : ""}</span>
            </div>
            <div style={{ display: "grid", gap: 8 }}>
              {cands.slice(0, candLimit).map((it) => {
                // 후보별 필요현금: 계산기 산식 그대로 (시가표준액=매물가 비례 추정)
                const std = inp.salePrice > 0
                  ? Math.floor(it.min_ask * (inp.standardPrice / inp.salePrice))
                  : Math.floor(it.min_ask * 0.7);
                // 대출금은 매물가 기준 규제 한도(LTV·가격별 캡)로 자동 캡핑
                const c = calculate({ ...inp, salePrice: it.min_ask, standardPrice: std,
                  loanAmount: effectiveLoan(inp, it.min_ask) });
                const feasible = c.cashGap >= 0;
                const disc = it.tx_avg ? (it.tx_avg - it.min_ask) / it.tx_avg : null;
                return (
                  <Link key={`${it.complex_no}-${it.area_name}`} to={`/complex/${it.complex_no}`}
                    style={{ border: `1px solid ${BORDER}`, borderRadius: 10, padding: "10px 12px",
                      background: "#fff", color: "inherit", textDecoration: "none", display: "block" }}>
                    <div style={{ display: "flex", gap: 8, alignItems: "baseline", flexWrap: "wrap" }}>
                      <b style={{ fontSize: 14.5 }}>{it.complex_name}</b><FavHeart complexNo={String(it.complex_no)} complexName={it.complex_name} />
                      <span className="muted" style={{ fontSize: 12 }}>{it.region}</span>
                      <span className="txf-b" style={{ background: feasible ? "#eefaf2" : "#fff7ea", color: feasible ? GREEN : "#c4791a" }}>
                        {feasible ? "가능" : "빠듯"}
                      </span>
                    </div>
                    <div style={{ display: "flex", gap: 12, flexWrap: "wrap", fontSize: 12.5, marginTop: 4 }}>
                      <span><b>{it.area_name}</b>{it.excl ? ` · ${areaLabel(it.excl)}` : ""}</span>
                      <span>호가 <b style={{ color: PRIMARY }}>{fmtEok(it.min_ask)}</b> ({it.n_ask}건)</span>
                      <span>실거래 12개월 {it.tx_avg ? fmtEok(it.tx_avg) : "없음"}{it.tx_n ? ` (${it.tx_n}건)` : ""}</span>
                      <span>필요현금 <b>{fmtEok(c.minRequiredCash)}</b></span>
                      {disc != null && (
                        <span style={{ color: disc >= 0.03 ? GREEN : disc <= -0.05 ? RED : "#64748b" }}>
                          {disc >= 0.03 ? `실거래 대비 ${(disc * 100).toFixed(1)}% 저렴` : disc <= -0.05 ? "실거래보다 높음" : "시세 수준"}
                        </span>
                      )}
                    </div>
                  </Link>
                );
              })}
              {cands.length === 0 && (
                <div className="muted" style={{ padding: 10 }}>조건에 맞는 매물이 없습니다. 지역·평형을 넓혀보세요.</div>
              )}
            </div>
            {cands.length > candLimit && (
              <button type="button" className="chip" style={{ marginTop: 10, width: "100%",
                display: "flex", alignItems: "center", justifyContent: "center",
                padding: "10px 0", fontSize: 13.5 }}
                onClick={() => setCandLimit((n) => n + 50)}>
                <ChevronDown size={14} style={{ verticalAlign: -3, marginRight: 4 }} />
                더보기 (남은 {cands.length - candLimit}건{cands.length >= 600 ? "+" : ""})
              </button>
            )}
          </div>
        )}
      </div>

      <div className="muted" style={{ fontSize: 11.5, marginBottom: 24 }}>
        본 계산기는 참고용입니다. 취득세·법무사 비용·국민주택채권 등은 개인 상황·지역·시기에 따라
        달라질 수 있으므로 실제 거래 전 전문가(세무사·법무사)와 확인하세요.
      </div>
    </div>
  );
}

// ---------------- 공용 소품 ----------------

function SecTitle({ children, step }: { children: React.ReactNode; step?: number }) {
  return (
    <div style={{ fontWeight: 800, fontSize: 15, marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
      {step != null && (
        <span style={{ display: "inline-flex", alignItems: "center", justifyContent: "center",
          width: 22, height: 22, borderRadius: 99, background: PRIMARY, color: "#fff",
          fontSize: 12.5, fontWeight: 800, flexShrink: 0 }}>{step}</span>
      )}
      <span style={{ display: "inline-flex", alignItems: "center" }}>{children}</span>
    </div>
  );
}

function Hint({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  // 마우스를 올리면 뜨고, 정보 영역을 벗어나면 사라짐(모바일은 탭으로 토글).
  return (
    <span style={{ position: "relative", display: "inline-flex" }}
      onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button type="button" aria-label="도움말"
        onClick={(e) => { e.preventDefault(); setOpen((o) => !o); }}
        onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}
        style={{ border: "none", background: "none", color: "#94a3b8", cursor: "pointer", padding: 0, display: "inline-flex" }}>
        <Info size={13.5} />
      </button>
      {open && (
        <span style={{ position: "absolute", zIndex: 30, top: 18, left: -80, width: 250, background: "#1e293b",
          color: "#f1f5f9", fontSize: 12, lineHeight: 1.55, padding: "9px 11px", borderRadius: 8,
          whiteSpace: "pre-line", boxShadow: "0 4px 14px rgba(0,0,0,.25)", pointerEvents: "none" }}>
          {text}
        </span>
      )}
    </span>
  );
}

/** 원 단위 금액 입력 + '+누적' 퀵버튼 (레퍼런스 AmountInputField 복제) */
function MoneyField({ label, value, quick, onSet, hint }: {
  label: string; value: number; quick: { l: string; v: number }[];
  onSet: (v: number) => void; hint?: string;
}) {
  return (
    <div>
      {label && <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 4 }}>{label}</div>}
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <input type="text" inputMode="numeric" value={value ? value.toLocaleString("ko-KR") : ""}
          placeholder="0"
          onChange={(e) => onSet(parseInt(e.target.value.replace(/[^\d]/g, ""), 10) || 0)}
          style={{ width: "100%", maxWidth: 220, padding: "9px 11px", border: `1px solid ${BORDER}`,
            borderRadius: 8, fontSize: 14.5, textAlign: "right", fontVariantNumeric: "tabular-nums" }} />
        <span style={{ fontSize: 14, fontWeight: 600 }}>원</span>
        <b style={{ fontSize: 12.5, color: PRIMARY, whiteSpace: "nowrap" }}>{fmtEok(value)}</b>
      </div>
      {quick.length > 0 && (
        <div style={{ display: "flex", gap: 5, marginTop: 6, flexWrap: "wrap" }}>
          {quick.map((q) => (
            <button key={q.l} type="button" onClick={() => onSet(value + q.v)}
              style={{ fontSize: 12, padding: "3px 11px", borderRadius: 99, border: `1px solid ${BORDER}`,
                background: "#fff", color: "#334155", cursor: "pointer", fontWeight: 600 }}>
              {q.l}
            </button>
          ))}
          <button type="button" onClick={() => onSet(0)}
            style={{ fontSize: 12, padding: "3px 11px", borderRadius: 99, border: `1px solid ${BORDER}`,
              background: "#fff", color: "#94a3b8", cursor: "pointer" }}>
            지우기
          </button>
        </div>
      )}
      {hint && <div className="muted" style={{ fontSize: 11.5, marginTop: 4 }}>{hint}</div>}
    </div>
  );
}

/** 가이드 금액으로 '설정'하는 칩 (퀵버튼의 +누적과 달리 값 지정) */
function SetChips({ value, onSet, amounts }: {
  value: number; onSet: (v: number) => void; amounts: [number, string][];
}) {
  return (
    <div style={{ display: "flex", gap: 5, marginTop: 6, flexWrap: "wrap" }}>
      {amounts.map(([v, l]) => (
        <button key={l} type="button" onClick={() => onSet(v)}
          style={{ fontSize: 12, padding: "3px 11px", borderRadius: 99,
            border: `1px solid ${value === v ? PRIMARY : BORDER}`,
            background: value === v ? "#e8f1fd" : "#fff",
            color: value === v ? PRIMARY : "#334155", cursor: "pointer", fontWeight: 600 }}>
          {l}
        </button>
      ))}
    </div>
  );
}

/** 대략적인 금액 가이드라인 — 정보(i) 버튼 클릭 시에만 펼침(페이지를 깔끔하게). */
function GuideBox({ title, rows, note }: {
  title: string; rows: [string, string][]; note?: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ marginTop: 2 }}>
      <button type="button" onClick={() => setOpen((o) => !o)}
        style={{ display: "inline-flex", alignItems: "center", gap: 4, background: "none",
          border: "none", color: PRIMARY, fontSize: 12, fontWeight: 600, cursor: "pointer", padding: "3px 0" }}>
        <Info size={13} /> {title}
        {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
      </button>
      {open && (
        <div style={{ background: "#f8fafc", border: `1px solid ${BORDER}`, borderRadius: 10,
          padding: "10px 12px", fontSize: 12.5, marginTop: 4 }}>
          <div style={{ display: "grid", gap: 3 }}>
            {rows.map(([k, v]) => (
              <div key={k} style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                <span style={{ color: "#64748b" }}>{k}</span>
                <b style={{ fontVariantNumeric: "tabular-nums", color: "#334155", whiteSpace: "nowrap" }}>{v}</b>
              </div>
            ))}
          </div>
          {note && <div className="muted" style={{ fontSize: 11.5, marginTop: 6, lineHeight: 1.55 }}>{note}</div>}
        </div>
      )}
    </div>
  );
}

function PresetRow({ label, options, value, onSelect }: {
  label: string; options: (readonly [string, string])[] | [string, string][];
  value: string; onSelect: (v: string) => void;
}) {
  return (
    <div>
      <div style={{ fontSize: 12.5, color: "#64748b", marginBottom: 5 }}>{label}</div>
      <div className="chip-row">
        {options.map(([k, l]) => (
          <button key={k} type="button" className={`chip ${value === k ? "active" : ""}`}
            onClick={() => onSelect(k)}>{l}</button>
        ))}
      </div>
    </div>
  );
}

function Collapsible({ title, children }: { title: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ ...CARD, marginBottom: 12, padding: 0 }}>
      <button type="button" onClick={() => setOpen(!open)}
        style={{ width: "100%", display: "flex", justifyContent: "space-between", alignItems: "center",
          padding: "13px 16px", background: "none", border: "none", cursor: "pointer", fontSize: 14, fontWeight: 700 }}>
        {title}
        {open ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
      </button>
      {open && <div style={{ padding: "0 16px 16px" }}>{children}</div>}
    </div>
  );
}

function RowKV({ k, v, sub, indent, strong }: {
  k: string; v: string; sub?: string; indent?: boolean; strong?: boolean;
}) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline",
      paddingLeft: indent ? 10 : 0, marginTop: 3 }}>
      <span style={{ fontSize: 13, color: strong ? "#0f172a" : "#64748b", fontWeight: strong ? 700 : 400 }}>
        {k}{sub && <span className="muted" style={{ fontSize: 11.5 }}> · {sub}</span>}
      </span>
      <span style={{ fontVariantNumeric: "tabular-nums", fontWeight: strong ? 800 : 600, fontSize: strong ? 14.5 : 13.5 }}>{v}</span>
    </div>
  );
}
