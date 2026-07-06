// 아파트매수마법사 (관리자 가오픈 2026-07-07) — "내 현금으로 실제 살 수 있는 단지"
// 진입 시 마법사(단계형 자동입력)/직접입력 선택 팝업 → 원페이지 폼 → 추천 결과.
// 검증 후 메인 오픈 예정. 계산·정책은 전부 서버(/admin/buywizard/*).
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Wand2, Calculator, ChevronLeft, ChevronRight, Loader2, Building2,
  Landmark, PiggyBank, MapPin, Ruler, BadgePercent, X,
} from "lucide-react";
import { useAuth } from "../auth";

const API_BASE = import.meta.env.VITE_API_BASE;
const PRIMARY = "#1268d3";
const BORDER = "#e4e9f0";
const SPIN: React.CSSProperties = { animation: "hp-spin .8s linear infinite" };
const PBTN: React.CSSProperties = { background: PRIMARY, color: "#fff", border: "none",
  borderRadius: 10, fontWeight: 700, cursor: "pointer" };

type Region = { code: string; name: string };
type RecItem = {
  complex_no: string; complex_name: string; region: string | null;
  area_name: string; excl: number | null; min_ask: number; n_ask: number;
  tx_avg: number | null; tx_n: number; tx_last: string | null; discount: number | null;
  households: number | null; approve_ymd: string | null;
  rooms_est: string; baths_est: string;
  leverage: number; required_cash: number; required_with_reserve: number;
  risk: string; score: number;
  costs: { tax_total: number; broker_fee: number; bond_cost: number;
    stamp_tax: number; legal_cost: number; costs_total: number; first_time_cut: number };
};
type RecResp = {
  max_price: number; jeonse_ratio: number | null; candidates_scanned: number;
  summary: null | { leverage: number; loan_info: Record<string, unknown>;
    costs: RecItem["costs"]; required_cash: number };
  items: RecItem[]; disclaimer: string;
};

const wonEok = (v: number | null | undefined) => {
  if (v == null) return "-";
  const e = Math.floor(v / 1e8), m = Math.round((v % 1e8) / 1e4);
  if (e && m) return `${e}억 ${m.toLocaleString()}`;
  if (e) return `${e}억`;
  return `${m.toLocaleString()}만`;
};
const RISK_C: Record<string, { bg: string; fg: string }> = {
  안정: { bg: "#eefaf2", fg: "#1f9d63" }, 보통: { bg: "#e8f1fd", fg: "#1268d3" },
  빠듯: { bg: "#fff7ea", fg: "#c4791a" }, 불가: { bg: "#fef2f2", fg: "#d23b3b" },
};

type Form = {
  purpose: "live" | "gap";
  buyer_type: "none" | "sell_one" | "keep_one" | "multi";
  is_first_time: boolean;
  cash_man: number;            // 만원
  income_man: number;          // 만원/년
  debt_pay_man: number;        // 만원/년
  sido: string; sigungus: Region[];
  area_min: number; area_max: number;
  rate_pct: number; years: number; preserve_man: number;
};
const DEFAULT_FORM: Form = {
  purpose: "live", buyer_type: "none", is_first_time: false,
  cash_man: 15000, income_man: 6000, debt_pay_man: 0,
  sido: "", sigungus: [], area_min: 59, area_max: 85,
  rate_pct: 4.2, years: 30, preserve_man: 1000,
};
const AREA_PRESETS = [
  { label: "~59㎡ (소형)", min: 0, max: 59 },
  { label: "59~85㎡ (국민평형)", min: 59, max: 85 },
  { label: "85~115㎡ (중대형)", min: 85, max: 115 },
  { label: "115㎡~ (대형)", min: 115, max: 300 },
];

export default function BuyWizard() {
  const { token } = useAuth();
  const [form, setForm] = useState<Form>(DEFAULT_FORM);
  const [mode, setMode] = useState<"ask" | "wizard" | "direct">("ask");
  const [step, setStep] = useState(0);
  const [sidos, setSidos] = useState<Region[]>([]);
  const [sggs, setSggs] = useState<Region[]>([]);
  const [loading, setLoading] = useState(false);
  const [res, setRes] = useState<RecResp | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    fetch(`${API_BASE}/stats/changes/sido-list`).then((r) => r.json())
      .then((j) => setSidos(j.items ?? [])).catch(() => {});
  }, []);
  useEffect(() => {
    if (!form.sido) { setSggs([]); return; }
    fetch(`${API_BASE}/stats/sigungu-list?sido=${form.sido.slice(0, 2)}`)
      .then((r) => r.json()).then((j) => setSggs(j.items ?? [])).catch(() => {});
  }, [form.sido]);

  const set = <K extends keyof Form>(k: K, v: Form[K]) => setForm((f) => ({ ...f, [k]: v }));
  const addSgg = (code: string) => {
    const r = sggs.find((s) => s.code === code);
    if (!r || form.sigungus.some((s) => s.code === code)) return;
    set("sigungus", [...form.sigungus, r]);
  };

  const run = async () => {
    if (!form.sigungus.length) { setErr("지역(시군구)을 1곳 이상 선택하세요"); return; }
    if (form.cash_man <= 0) { setErr("보유현금을 입력하세요"); return; }
    setErr(""); setLoading(true); setRes(null);
    try {
      const body = {
        cash_on_hand: form.cash_man * 10000,
        annual_income: form.income_man * 10000,
        existing_annual_payment: form.debt_pay_man * 10000,
        buyer_type: form.buyer_type,
        is_first_time: form.is_first_time,
        purpose: form.purpose,
        region_codes: form.sigungus.map((s) => s.code.slice(0, 5)),
        dong_codes: [],
        area_min: form.area_min, area_max: form.area_max,
        mortgage_rate: form.rate_pct / 100, loan_years: form.years,
        preserve_cash: form.preserve_man * 10000,
      };
      const r = await fetch(`${API_BASE}/admin/buywizard/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      });
      if (!r.ok) throw new Error(`${r.status}`);
      setRes(await r.json());
    } catch (e) {
      setErr(`계산 실패: ${e}`);
    } finally {
      setLoading(false);
    }
  };

  // ---- 마법사 단계 정의 ----
  const steps: { title: string; body: React.ReactNode; ok?: () => boolean }[] = [
    {
      title: "어떤 방식의 매수인가요?",
      body: (
        <div className="chip-row">
          {([["live", "실거주 (대출 활용)"], ["gap", "전세 끼고 매수 (갭)"]] as const).map(([k, l]) => (
            <button key={k} type="button" className={`chip ${form.purpose === k ? "active" : ""}`}
              onClick={() => set("purpose", k)}>{l}</button>
          ))}
        </div>
      ),
    },
    {
      title: "현재 주택 보유 상황은요?",
      body: (
        <>
          <div className="chip-row" style={{ marginBottom: 10 }}>
            {([["none", "무주택"], ["sell_one", "1주택 (처분 예정)"],
              ["keep_one", "1주택 (유지)"], ["multi", "다주택"]] as const).map(([k, l]) => (
              <button key={k} type="button" className={`chip ${form.buyer_type === k ? "active" : ""}`}
                onClick={() => set("buyer_type", k)}>{l}</button>
            ))}
          </div>
          {(form.buyer_type === "none" || form.buyer_type === "sell_one") && (
            <label style={{ fontSize: 13.5, display: "flex", gap: 6, alignItems: "center" }}>
              <input type="checkbox" checked={form.is_first_time}
                onChange={(e) => set("is_first_time", e.target.checked)} />
              생애최초 주택 구입입니다 (LTV 우대·취득세 감면 반영)
            </label>
          )}
        </>
      ),
    },
    {
      title: "보유 현금은 얼마인가요?",
      body: (
        <MoneyInput label="보유현금" man={form.cash_man} onChange={(v) => set("cash_man", v)}
          quick={[5000, 10000, 20000, 30000]} />
      ),
      ok: () => form.cash_man > 0,
    },
    {
      title: "연소득과 기존 대출을 알려주세요",
      body: (
        <>
          <MoneyInput label="세전 연소득" man={form.income_man} onChange={(v) => set("income_man", v)}
            quick={[4000, 6000, 8000, 10000]} />
          <MoneyInput label="기존대출 연 원리금 상환액" man={form.debt_pay_man}
            onChange={(v) => set("debt_pay_man", v)} quick={[0, 500, 1000]} />
          <div className="muted" style={{ fontSize: 12 }}>
            신용대출·자동차할부 등 매년 갚는 원리금 합계. DSR 한도에서 차감됩니다.
          </div>
        </>
      ),
    },
    {
      title: "어느 지역을 보고 있나요?",
      body: <RegionPicker form={form} set={set} sidos={sidos} sggs={sggs} addSgg={addSgg} />,
      ok: () => form.sigungus.length > 0,
    },
    {
      title: "희망 평형은요?",
      body: (
        <div className="chip-row">
          {AREA_PRESETS.map((p) => (
            <button key={p.label} type="button"
              className={`chip ${form.area_min === p.min && form.area_max === p.max ? "active" : ""}`}
              onClick={() => { set("area_min", p.min); set("area_max", p.max); }}>
              {p.label}
            </button>
          ))}
        </div>
      ),
    },
    {
      title: "대출 가정 (기본값 그대로 두셔도 됩니다)",
      body: (
        <div style={{ display: "grid", gap: 10 }}>
          <NumInput label="예상 주담대 금리(%)" value={form.rate_pct} step={0.1}
            onChange={(v) => set("rate_pct", v)} />
          <NumInput label="만기(년)" value={form.years} step={5}
            onChange={(v) => set("years", v)} />
          <MoneyInput label="남겨둘 예비비" man={form.preserve_man}
            onChange={(v) => set("preserve_man", v)} quick={[500, 1000, 2000]} />
        </div>
      ),
    },
  ];

  return (
    <div className="page" style={{ maxWidth: 860 }}>
      <Link to="/admin" style={{ fontSize: 13, color: "#64748b", display: "inline-flex", alignItems: "center", gap: 2 }}>
        <ChevronLeft size={14} /> 관리자
      </Link>
      <h1 style={{ display: "flex", alignItems: "center", gap: 8, margin: "6px 0 2px" }}>
        <Wand2 size={22} color={PRIMARY} /> 아파트매수마법사
        <span className="txf-b" style={{ background: "#fff7ea", color: "#c4791a" }}>관리자 가오픈</span>
      </h1>
      <div className="muted" style={{ marginBottom: 14 }}>
        대출한도(LTV·DSR·지역별 캡)와 취득세·중개보수·채권·등기비까지 반영해
        <b> 실제 살 수 있는 단지</b>를 찾아드립니다.
      </div>

      {/* 진입 선택 팝업 */}
      {mode === "ask" && (
        <div className="modal-overlay">
          <div className="modal-card" style={{ maxWidth: 400, textAlign: "center" }}>
            <Wand2 size={34} color={PRIMARY} style={{ margin: "6px auto 10px" }} />
            <div style={{ fontSize: 17, fontWeight: 800, marginBottom: 6 }}>
              입력이 많아요. 마법사로 진행할까요?
            </div>
            <div className="muted" style={{ fontSize: 13, marginBottom: 16 }}>
              7개 질문에 하나씩 답하면 자동으로 채워드립니다.<br />
              익숙하시면 한 페이지에서 직접 입력할 수도 있어요.
            </div>
            <div style={{ display: "grid", gap: 8 }}>
              <button type="button" style={{ ...PBTN,  padding: "11px 0", fontSize: 15 }}
                onClick={() => { setMode("wizard"); setStep(0); }}>
                <Wand2 size={15} style={{ verticalAlign: -2, marginRight: 5 }} />마법사로 시작
              </button>
              <button type="button" className="chip" style={{ padding: "10px 0", fontSize: 14 }}
                onClick={() => setMode("direct")}>
                <Calculator size={14} style={{ verticalAlign: -2, marginRight: 5 }} />직접 입력할게요
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 마법사 모달 */}
      {mode === "wizard" && (
        <div className="modal-overlay">
          <div className="modal-card" style={{ maxWidth: 460 }}>
            <div className="modal-head">
              <span className="modal-title">단계 {step + 1} / {steps.length}</span>
              <button className="phone-banner-x" aria-label="닫기" onClick={() => setMode("direct")}><X size={16} /></button>
            </div>
            <div style={{ height: 4, background: "#eef2f7", borderRadius: 99, margin: "4px 0 14px" }}>
              <div style={{ height: 4, width: `${((step + 1) / steps.length) * 100}%`, background: PRIMARY, borderRadius: 99 }} />
            </div>
            <div style={{ fontSize: 16, fontWeight: 800, marginBottom: 12 }}>{steps[step].title}</div>
            <div style={{ minHeight: 90 }}>{steps[step].body}</div>
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 16 }}>
              <button type="button" className="chip" disabled={step === 0}
                onClick={() => setStep((s) => Math.max(0, s - 1))}>
                <ChevronLeft size={14} style={{ verticalAlign: -2 }} />이전
              </button>
              {step < steps.length - 1 ? (
                <button type="button" style={{ ...PBTN,  padding: "8px 18px" }}
                  disabled={steps[step].ok ? !steps[step].ok!() : false}
                  onClick={() => setStep((s) => s + 1)}>
                  다음<ChevronRight size={14} style={{ verticalAlign: -2 }} />
                </button>
              ) : (
                <button type="button" style={{ ...PBTN,  padding: "8px 18px" }}
                  onClick={() => { setMode("direct"); run(); }}>
                  계산하기
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 원페이지 폼 */}
      <div style={{ border: `1px solid ${BORDER}`, borderRadius: 14, padding: 16, background: "#fff", marginBottom: 16 }}>
        <Sec icon={<PiggyBank size={15} color={PRIMARY} />} title="자금" />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10 }}>
          <MoneyInput label="보유현금" man={form.cash_man} onChange={(v) => set("cash_man", v)} quick={[10000, 20000]} />
          <MoneyInput label="세전 연소득" man={form.income_man} onChange={(v) => set("income_man", v)} quick={[6000, 8000]} />
          <MoneyInput label="기존대출 연 상환액" man={form.debt_pay_man} onChange={(v) => set("debt_pay_man", v)} quick={[0]} />
          <MoneyInput label="예비비(남길 돈)" man={form.preserve_man} onChange={(v) => set("preserve_man", v)} quick={[1000, 2000]} />
        </div>

        <Sec icon={<Landmark size={15} color={PRIMARY} />} title="주택 상황" top />
        <div className="chip-row">
          {([["none", "무주택"], ["sell_one", "1주택 처분예정"], ["keep_one", "1주택 유지"], ["multi", "다주택"]] as const).map(([k, l]) => (
            <button key={k} type="button" className={`chip ${form.buyer_type === k ? "active" : ""}`}
              onClick={() => set("buyer_type", k)}>{l}</button>
          ))}
          {(form.buyer_type === "none" || form.buyer_type === "sell_one") && (
            <label className="chip" style={{ display: "inline-flex", gap: 5, alignItems: "center", cursor: "pointer" }}>
              <input type="checkbox" checked={form.is_first_time}
                onChange={(e) => set("is_first_time", e.target.checked)} /> 생애최초
            </label>
          )}
          {([["live", "실거주(대출)"], ["gap", "전세끼고(갭)"]] as const).map(([k, l]) => (
            <button key={k} type="button" className={`chip ${form.purpose === k ? "active" : ""}`}
              style={{ marginLeft: k === "live" ? 12 : 0 }}
              onClick={() => set("purpose", k)}>{l}</button>
          ))}
        </div>

        <Sec icon={<MapPin size={15} color={PRIMARY} />} title="희망 지역" top />
        <RegionPicker form={form} set={set} sidos={sidos} sggs={sggs} addSgg={addSgg} />

        <Sec icon={<Ruler size={15} color={PRIMARY} />} title="희망 평형 (전용면적)" top />
        <div className="chip-row">
          {AREA_PRESETS.map((p) => (
            <button key={p.label} type="button"
              className={`chip ${form.area_min === p.min && form.area_max === p.max ? "active" : ""}`}
              onClick={() => { set("area_min", p.min); set("area_max", p.max); }}>{p.label}</button>
          ))}
        </div>

        <Sec icon={<BadgePercent size={15} color={PRIMARY} />} title="대출 가정" top />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10 }}>
          <NumInput label="주담대 금리(%)" value={form.rate_pct} step={0.1} onChange={(v) => set("rate_pct", v)} />
          <NumInput label="만기(년)" value={form.years} step={5} onChange={(v) => set("years", v)} />
        </div>

        <div style={{ marginTop: 16, display: "flex", gap: 8, alignItems: "center" }}>
          <button type="button" style={{ ...PBTN,  padding: "11px 26px", fontSize: 15 }}
            disabled={loading} onClick={run}>
            {loading ? <Loader2 size={15} style={SPIN} /> : <Calculator size={15} style={{ verticalAlign: -2 }} />}
            {" "}구매 가능 단지 찾기
          </button>
          <button type="button" className="chip" onClick={() => { setMode("wizard"); setStep(0); }}>
            <Wand2 size={13} style={{ verticalAlign: -2 }} /> 마법사 다시
          </button>
          {err && <span style={{ color: "#d23b3b", fontSize: 13 }}>{err}</span>}
        </div>
      </div>

      {/* 결과 */}
      {res && <Result res={res} cashMan={form.cash_man} />}
    </div>
  );
}

function Sec({ icon, title, top }: { icon: React.ReactNode; title: string; top?: boolean }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 800, fontSize: 14,
      margin: top ? "16px 0 8px" : "0 0 8px" }}>
      {icon}{title}
    </div>
  );
}

function MoneyInput({ label, man, onChange, quick }: {
  label: string; man: number; onChange: (v: number) => void; quick?: number[];
}) {
  return (
    <div>
      <div style={{ fontSize: 12.5, color: "#64748b", marginBottom: 4 }}>{label}</div>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <input type="text" inputMode="numeric" value={man ? man.toLocaleString() : ""}
          placeholder="0"
          onChange={(e) => onChange(parseInt(e.target.value.replace(/[^0-9]/g, ""), 10) || 0)}
          style={{ width: "100%", maxWidth: 140, padding: "8px 10px", border: `1px solid ${BORDER}`,
            borderRadius: 8, fontSize: 14, textAlign: "right", fontVariantNumeric: "tabular-nums" }} />
        <span style={{ fontSize: 13, color: "#64748b", whiteSpace: "nowrap" }}>만원</span>
        <b style={{ fontSize: 12.5, color: PRIMARY, whiteSpace: "nowrap" }}>{wonEok(man * 10000)}</b>
      </div>
      {quick && (
        <div style={{ display: "flex", gap: 4, marginTop: 4, flexWrap: "wrap" }}>
          {quick.map((q) => (
            <button key={q} type="button" onClick={() => onChange(q)}
              style={{ fontSize: 11.5, padding: "2px 8px", borderRadius: 99, border: `1px solid ${BORDER}`,
                background: man === q ? "#e8f1fd" : "#fff", color: "#475569", cursor: "pointer" }}>
              {wonEok(q * 10000)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function NumInput({ label, value, step, onChange }: {
  label: string; value: number; step: number; onChange: (v: number) => void;
}) {
  return (
    <div>
      <div style={{ fontSize: 12.5, color: "#64748b", marginBottom: 4 }}>{label}</div>
      <input type="number" value={value} step={step}
        onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
        style={{ width: "100%", maxWidth: 120, padding: "8px 10px", border: `1px solid ${BORDER}`,
          borderRadius: 8, fontSize: 14, textAlign: "right" }} />
    </div>
  );
}

function RegionPicker({ form, set, sidos, sggs, addSgg }: {
  form: Form; set: <K extends keyof Form>(k: K, v: Form[K]) => void;
  sidos: Region[]; sggs: Region[]; addSgg: (code: string) => void;
}) {
  return (
    <div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <select value={form.sido} onChange={(e) => set("sido", e.target.value)}
          style={{ padding: "8px 10px", border: `1px solid ${BORDER}`, borderRadius: 8, fontSize: 14 }}>
          <option value="">시·도 선택</option>
          {sidos.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
        </select>
        <select value="" onChange={(e) => addSgg(e.target.value)} disabled={!form.sido}
          style={{ padding: "8px 10px", border: `1px solid ${BORDER}`, borderRadius: 8, fontSize: 14 }}>
          <option value="">시·군·구 추가</option>
          {sggs.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
        </select>
      </div>
      {form.sigungus.length > 0 && (
        <div className="chip-row" style={{ marginTop: 8 }}>
          {form.sigungus.map((s) => (
            <span key={s.code} className="chip active" style={{ display: "inline-flex", gap: 4, alignItems: "center" }}>
              {s.name}
              <X size={12} style={{ cursor: "pointer" }}
                onClick={() => set("sigungus", form.sigungus.filter((x) => x.code !== s.code))} />
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function Result({ res, cashMan }: { res: RecResp; cashMan: number }) {
  const s = res.summary;
  const best84 = useMemo(() => res.items.find((i) => (i.excl ?? 0) >= 80), [res.items]);
  if (!res.max_price) {
    return (
      <div style={{ border: `1px solid ${BORDER}`, borderRadius: 14, padding: 20, background: "#fff" }}>
        <b>현재 조건으로는 구매 가능한 가격대가 없습니다.</b>
        <div className="muted" style={{ marginTop: 6, fontSize: 13 }}>
          보유현금·예비비 설정을 조정하거나, 전세 끼고 매수(갭) 방식을 검토해 보세요.
        </div>
      </div>
    );
  }
  return (
    <>
      <div style={{ border: `1px solid ${BORDER}`, borderRadius: 14, padding: 18, background: "#f6faff", marginBottom: 12 }}>
        <div style={{ fontSize: 13, color: "#64748b" }}>현재 조건으로</div>
        <div style={{ fontSize: 24, fontWeight: 800, color: PRIMARY, margin: "2px 0 8px" }}>
          약 {wonEok(res.max_price)}까지 구매 가능
        </div>
        {s && (
          <div style={{ fontSize: 13.5, color: "#334155", lineHeight: 1.6 }}>
            보유현금 {wonEok(cashMan * 10000)} 기준 —
            {" "}{res.jeonse_ratio ? `전세가율 ${(res.jeonse_ratio * 100).toFixed(0)}% 레버리지` : `대출 약 ${wonEok(s.leverage)}`},
            취득세 등 부대비용 약 <b>{wonEok(s.costs.costs_total)}</b>
            {s.costs.first_time_cut > 0 && ` (생애최초 감면 ${wonEok(s.costs.first_time_cut)} 반영)`} 포함.
            {best84 == null && res.items.length > 0 && " 중대형(84㎡+)은 빠듯하고 아래 평형이 현실적입니다."}
          </div>
        )}
        <div className="muted" style={{ fontSize: 11.5, marginTop: 8 }}>{res.disclaimer}</div>
      </div>

      <div style={{ fontWeight: 800, fontSize: 15, margin: "0 0 8px" }}>
        추천 단지 {res.items.length}곳 <span className="muted" style={{ fontWeight: 400, fontSize: 12.5 }}>
          (매물 {res.candidates_scanned}건 검토 · 점수순)</span>
      </div>
      <div style={{ display: "grid", gap: 10 }}>
        {res.items.map((it, i) => {
          const rc = RISK_C[it.risk] ?? RISK_C["보통"];
          return (
            <Link key={`${it.complex_no}-${it.area_name}`} to={`/complex/${it.complex_no}`}
              style={{ border: `1px solid ${BORDER}`, borderRadius: 12, padding: "12px 14px",
                background: "#fff", color: "inherit", textDecoration: "none", display: "block" }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
                <span style={{ fontSize: 12, color: "#94a3b8", fontWeight: 700 }}>{i + 1}</span>
                <b style={{ fontSize: 15.5 }}><Building2 size={13} style={{ verticalAlign: -1.5, marginRight: 3, color: PRIMARY }} />
                  {it.complex_name}</b>
                <span className="muted" style={{ fontSize: 12.5 }}>{it.region}</span>
                <span className="txf-b" style={{ background: rc.bg, color: rc.fg }}>{it.risk}</span>
                <span style={{ marginLeft: "auto", fontSize: 12, color: "#8296ab" }}>{it.score}점</span>
              </div>
              <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginTop: 7, fontSize: 13 }}>
                <span><b>{it.area_name}</b>{it.excl ? ` · 전용 ${Math.round(it.excl)}㎡` : ""}
                  <span className="muted"> · 방{it.rooms_est}/욕{it.baths_est}(추정)</span></span>
                <span>호가 <b style={{ color: PRIMARY }}>{wonEok(it.min_ask)}</b>
                  <span className="muted"> ({it.n_ask}건)</span></span>
                <span>실거래 12개월 {it.tx_avg ? <b>{wonEok(it.tx_avg)}</b> : <span className="muted">없음</span>}
                  {it.tx_n > 0 && <span className="muted"> ({it.tx_n}건)</span>}</span>
                <span>필요현금 <b style={{ color: "#0f172a" }}>{wonEok(it.required_with_reserve)}</b></span>
              </div>
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 5, fontSize: 12, color: "#64748b" }}>
                {it.discount != null && (
                  <span style={{ color: it.discount >= 0.03 ? "#1f9d63" : it.discount <= -0.05 ? "#d23b3b" : "#64748b" }}>
                    {it.discount >= 0.03 ? `실거래 대비 ${(it.discount * 100).toFixed(1)}% 저렴`
                      : it.discount <= -0.05 ? "실거래보다 높음 — 협상 필요" : "시세 수준"}
                  </span>
                )}
                {it.tx_avg == null && <span>실거래 부족 — 보수적으로 판단</span>}
                {it.households ? <span>{it.households.toLocaleString()}세대</span> : null}
                {it.approve_ymd ? <span>준공 {String(it.approve_ymd).slice(0, 4)}</span> : null}
                <span>대출 {wonEok(it.leverage)} · 세금 {wonEok(it.costs.tax_total)} · 중개보수 {wonEok(it.costs.broker_fee)}</span>
              </div>
            </Link>
          );
        })}
        {res.items.length === 0 && (
          <div className="muted" style={{ padding: 16 }}>조건에 맞는 매물이 없습니다. 지역·평형을 넓혀보세요.</div>
        )}
      </div>
    </>
  );
}
