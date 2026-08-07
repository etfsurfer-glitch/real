// 대시보드 빠른 입력 — 자연어로 치거나 문자·카톡을 붙여넣으면 매물/고객이 된다.
// 설계안 design/lounge_customer_ledger_설계안.md §2-2 §4-2 §4-3.
//
// 흐름: ① 입력 → ② 확인(자동으로 채운 값을 근거와 함께) → ③ 저장.
// 확인을 건너뛰지 않는다 — 근거 없는 값을 그냥 믿으라고 요구하지 않기 위해서다.
import { useState } from "react";
import { Sparkles, Loader2, Check, X, Building2, UserRound, Lock, AlertTriangle, Link2, Search } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE;

type Auto = Record<string, string>;
type Cand = { complex_no: string; name: string; region: string };
type ListingRow = Record<string, any> & {
  _auto?: Auto; _area_name_cands?: string[]; _note?: string; _complex_cands?: Cand[];
};
type Need = Record<string, any>;
type CustomerRow = { name?: string; phone?: string; memo?: string; 요건?: Need[] };
type Parsed = {
  매물?: ListingRow[]; 고객?: CustomerRow[];
  확신낮음?: string[]; 못읽은줄?: string[];
};

// 매물과 고객을 나눠 받지 않는다. 매물 정보에는 임대인·매도인이 딸려 오고,
// 손님 메시지에는 내놓을 물건이 딸려 온다 — 나누면 같은 글을 두 번 넣게 된다.
const PLACEHOLDER =
  "매물이든 손님이든 그냥 적으시면 됩니다. 문자·카톡을 붙여넣어도 돼요.\n\n" +
  "탕정푸르지오리버파크 205동 1503호 전세 3억5천 임대인 김소연 010-9999-1111";
const EXAMPLES = [
  "고덕그라시움 142동 2004호 매매 24억 올수리 남향 즉시입주 매도인 박영희 010-2222-3333",
  "김철수 010-3001-0001 고덕동 34평 매매 24~27억 10월 입주 희망",
];

const won = (v: any): string => {
  const n = Number(v);
  if (!n) return "";
  if (n >= 1e8) {
    const e = Math.floor(n / 1e8), m = Math.round((n % 1e8) / 1e4);
    return m ? `${e}억 ${m.toLocaleString()}만` : `${e}억`;
  }
  return `${Math.round(n / 1e4).toLocaleString()}만`;
};
const TRADE_KOR: Record<string, string> = { A1: "매매", B1: "전세", B2: "월세" };

// 금액은 원 단위 정수로 저장하지만, 중개사에게 2400000000 을 치라고 할 수는 없다.
// '24억' '3억5천' '1,000만' 을 그대로 받고, 옆에 환산값을 보여줘 확인하게 한다.
function parseWon(raw: string): number | null {
  const t = (raw || "").replace(/[\s,]/g, "");
  if (!t) return null;
  if (/^\d+$/.test(t)) return Number(t);          // 숫자만 → 원 단위 그대로
  let v = 0, matched = false;
  const eok = t.match(/(\d+(?:\.\d+)?)억/);
  if (eok) { v += parseFloat(eok[1]) * 1e8; matched = true; }
  const chun = t.match(/억(\d+(?:\.\d+)?)천/) || (!eok && t.match(/(\d+(?:\.\d+)?)천/));
  if (chun) { v += parseFloat(chun[1]) * 1e7; matched = true; }
  const man = t.match(/(\d+(?:\.\d+)?)만/);
  if (man && !chun) { v += parseFloat(man[1]) * 1e4; matched = true; }
  else if (eok && !chun) {
    const rest = t.slice(t.indexOf("억") + 1).match(/^(\d+)$/);   // '24억 5000' 처럼 뒤가 숫자만
    if (rest) { v += Number(rest[1]) * 1e4; matched = true; }
  }
  return matched ? Math.round(v) : null;
}

type FType = "text" | "money" | "num" | "trade";
// 매물 항목 — 키, 라벨(고정 또는 행에 따라), 입력 종류, 단위 표시
const L_FIELDS: [string, string | ((r: ListingRow) => string), FType, string?][] = [
  ["complex_name", "단지", "text"],
  ["address", "주소", "text"],
  ["dong", "동", "text"],
  ["ho", "호", "text"],
  ["trade_type", "거래", "trade"],
  ["price", "매매가", "money"],
  ["deposit", "보증금", "money"],
  ["rent_price", "월세", "money"],
  ["area2_m2", "전용", "num", "㎡"],
  ["floor", "층", "num", "층"],
  ["room_cnt", "방", "num", "개"],
  ["bath_cnt", "욕실", "num", "개"],
  ["direction", "향", "text"],
  ["settle_ymd", "잔금시기", "text"],
  ["move_in", "입주가능", "text"],
  ["maintenance_fee", "관리비", "money"],
  ["approve_ymd", "준공", "text"],
  ["parking", "주차", "num", "대"],
  ["owner_name", (r) => ownerLabel(r.trade_type), "text"],
  ["owner_tel", (r) => `${ownerLabel(r.trade_type)} 연락처`, "text"],
  ["feature_desc", "특징", "text"],
  ["memo", "메모", "text"],
];
const N_FIELDS: [string, string, FType][] = [
  ["kind", "구분", "text"], ["trade", "거래", "trade"], ["role", "역할", "text"],
  ["budget_min", "예산 최소", "money"], ["budget_max", "예산 최대", "money"],
  ["ask_price", "내놓은 가격", "money"],
  ["region", "지역", "text"], ["complex_name", "단지", "text"],
  ["area_min", "면적 최소", "num"], ["area_max", "면적 최대", "num"],
  ["settle_date", "잔금시기", "text"],
];

// 유형을 못 읽었을 때만 물어본다. 유형에 따라 단지 매칭 여부·건축물대장 조회 경로·
// 광고 필수항목이 갈리므로 비어 있으면 뒤가 전부 어긋난다. 대개는 문장이나 단지 DB 에서
// 채워지므로 이 칩은 잘 안 뜬다 — 늘 고르게 하면 손만 늘어난다.
const QA_TYPES = ["아파트", "오피스텔", "빌라", "원룸", "단독", "상가", "사무실", "토지"];

// 소유자 호칭은 거래유형에 따라 달라진다. 전세·월세 물건의 소유자는 매도인이 아니라 임대인이다.
// 거래를 모를 때만 중립어(소유자)를 쓴다 — 기존 매물장 폼과 같은 말.
function ownerLabel(trade: any): string {
  const t = String(trade || "");
  if (t === "매매" || t === "A1") return "매도인";
  if (t === "전세" || t === "월세" || t === "B1" || t === "B2") return "임대인";
  return "소유자";
}

/** 편집 가능한 한 칸. 자동으로 채운 값도 고칠 수 있다 — 대장이 실제와 다를 수 있다.
 *  고치면 자물쇠(자동) 표시가 사라진다. 사람이 정한 값이라는 뜻이다. */
function Cell({ label, type, unit, value, auto, low, onChange }: {
  label: string; type: FType; unit?: string; value: any;
  auto?: string; low?: boolean; onChange: (v: any) => void;
}) {
  // 금액은 사람이 읽는 표기로 들고 있다가 저장 직전에 숫자로 바꾼다
  const [draft, setDraft] = useState<string | null>(null);
  const shown = draft !== null ? draft : (type === "money" ? won(value) : value ?? "");
  const commit = (t: string) => {
    setDraft(null);
    if (type === "money") onChange(parseWon(t));
    else if (type === "num") onChange(t.trim() === "" ? null : Number(t.replace(/[^\d.]/g, "")) || null);
    else onChange(t.trim() === "" ? null : t);
  };
  const filled = value !== null && value !== undefined && value !== "";
  return (
    <label className={"qadd-f" + (auto ? " auto" : "") + (low ? " low" : "") + (filled ? "" : " empty")}>
      <span>{label}</span>
      {type === "trade" ? (
        <select value={TRADE_KOR[value] || value || ""} onChange={(e) => onChange(e.target.value || null)}>
          <option value="">-</option>
          {["매매", "전세", "월세"].map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      ) : (
        <input
          value={String(shown ?? "")} inputMode={type === "text" ? undefined : "decimal"}
          placeholder={type === "money" ? "예: 24억" : unit ? `0${unit}` : ""}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={(e) => commit(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }} />
      )}
      {unit && type === "num" && filled && <i>{unit}</i>}
      {type === "money" && draft !== null && parseWon(draft) != null && <i>{won(parseWon(draft))}</i>}
      {auto && draft === null && <em title={`${auto}에서 자동으로 채웠어요`}><Lock size={10} /> {auto}</em>}
    </label>
  );
}


export default function QuickAdd({ authH, onSaved }: {
  authH: () => Record<string, string>; onSaved?: () => void;
}) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [parsed, setParsed] = useState<Parsed | null>(null);
  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState("");
  // 저장에서 뺄 항목(체크 해제). 기본은 전부 저장 — 뺄 일이 드물다
  const [offL, setOffL] = useState<Set<number>>(new Set());
  const [offC, setOffC] = useState<Set<number>>(new Set());

  const [showAll, setShowAll] = useState(false);   // 빈 칸까지 펼치기

  const reset = () => {
    setParsed(null); setErr(""); setDone(""); setOffL(new Set()); setOffC(new Set()); setShowAll(false);
  };

  // 단지 후보 중 하나를 고르면 그 단지 기준으로 다시 채운다
  const [enriching, setEnriching] = useState<number | null>(null);
  // 후보에도 없으면 중개사가 직접 찾아 넣는다
  const [cxOpen, setCxOpen] = useState<number | null>(null);
  const [cxQ, setCxQ] = useState("");
  const [cxHits, setCxHits] = useState<{ complex_no: string; complex_name: string; region?: string; households?: number }[]>([]);
  const [cxBusy, setCxBusy] = useState(false);
  const searchComplex = async () => {
    if (cxQ.trim().length < 2 || cxBusy) return;
    setCxBusy(true);
    try {
      const r = await fetch(`${API_BASE}/lounge/complex-search?q=${encodeURIComponent(cxQ)}`, { headers: authH() });
      const j = await r.json();
      setCxHits(j.items ?? []);
    } catch { setCxHits([]); } finally { setCxBusy(false); }
  };
  const pickComplex = async (i: number, complex_no: string) => {
    if (!parsed || enriching !== null) return;
    setEnriching(i); setErr(""); setCxOpen(null); setCxHits([]); setCxQ("");
    try {
      const res = await fetch(`${API_BASE}/lounge/quick-enrich`, {
        method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
        body: JSON.stringify({ row: parsed.매물![i], complex_no }),
      });
      const j = await res.json();
      if (!res.ok) throw new Error(j?.detail || `오류 ${res.status}`);
      setParsed((prev) => {
        if (!prev) return prev;
        const 매물 = [...(prev.매물 || [])];
        매물[i] = j.row;
        return { ...prev, 매물 };
      });
    } catch (e: any) {
      setErr(e?.message || "단지 정보를 가져오지 못했어요");
    } finally { setEnriching(null); }
  };

  // 편집 — 고치면 그 칸의 '자동' 표식을 뗀다. 사람이 정한 값이라는 뜻이다.
  const editL = (i: number, k: string, v: any) => setParsed((prev) => {
    if (!prev) return prev;
    const 매물 = [...(prev.매물 || [])];
    const row = { ...매물[i], [k]: v };
    if (row._auto?.[k]) { row._auto = { ...row._auto }; delete row._auto[k]; }
    매물[i] = row;
    return { ...prev, 매물 };
  });
  const editC = (i: number, k: string, v: any) => setParsed((prev) => {
    if (!prev) return prev;
    const 고객 = [...(prev.고객 || [])];
    고객[i] = { ...고객[i], [k]: v };
    return { ...prev, 고객 };
  });
  const editN = (ci: number, ni: number, k: string, v: any) => setParsed((prev) => {
    if (!prev) return prev;
    const 고객 = [...(prev.고객 || [])];
    const needs = [...(고객[ci].요건 || [])];
    needs[ni] = { ...needs[ni], [k]: v };
    고객[ci] = { ...고객[ci], 요건: needs };
    return { ...prev, 고객 };
  });
  const toggle = (s: Set<number>, set: (v: Set<number>) => void, i: number) => {
    const n = new Set(s); n.has(i) ? n.delete(i) : n.add(i); set(n);
  };

  const run = async () => {
    if (!text.trim() || busy) return;
    setBusy(true); setErr(""); setParsed(null); setDone("");
    try {
      const r = await fetch(`${API_BASE}/lounge/quick-parse`, {
        method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j?.detail || `오류 ${r.status}`);
      setParsed(j);
    } catch (e: any) {
      setErr(e?.message || "인식에 실패했어요");
    } finally { setBusy(false); }
  };

  // 매물을 빼면 그 매물을 가리키던 요건의 연결(매물번호)이 어긋난다 → 인덱스를 다시 매긴다
  const save = async () => {
    if (!parsed || saving) return;
    const keptL = (parsed.매물 || []).filter((_, i) => !offL.has(i));
    const remap = new Map<number, number>();
    (parsed.매물 || []).forEach((_, i) => { if (!offL.has(i)) remap.set(i, remap.size); });
    const keptC = (parsed.고객 || []).filter((_, i) => !offC.has(i)).map((c) => ({
      ...c,
      요건: (c.요건 || []).map((n) => ({
        ...n,
        매물번호: typeof n.매물번호 === "number" ? (remap.has(n.매물번호) ? remap.get(n.매물번호) : null) : null,
      })),
    }));
    if (!keptL.length && !keptC.length) { setErr("저장할 항목을 하나 이상 골라 주세요"); return; }
    setSaving(true); setErr("");
    try {
      const clean = keptL.map((r) => {
        const o: Record<string, any> = {};
        for (const [k, v] of Object.entries(r)) if (!k.startsWith("_") && v !== null && v !== "") o[k] = v;
        return o;
      });
      const res = await fetch(`${API_BASE}/lounge/quick-save`, {
        method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
        body: JSON.stringify({ 매물: clean, 고객: keptC, raw_text: text }),
      });
      const j = await res.json();
      if (!res.ok) throw new Error(j?.detail || `저장 실패 (${res.status})`);
      setDone([j.listings ? `매물 ${j.listings}건` : "", j.customers ? `고객 ${j.customers}명` : ""]
        .filter(Boolean).join(" · ") + " 저장했어요");
      setParsed(null); setText(""); setOffL(new Set()); setOffC(new Set());
      onSaved?.();
    } catch (e: any) {
      setErr(e?.message || "저장에 실패했어요");
    } finally { setSaving(false); }
  };

  const lowConf = new Set(parsed?.확신낮음 || []);
  const nL = (parsed?.매물 || []).length - offL.size;
  const nC = (parsed?.고객 || []).length - offC.size;

  return (
    <div className="qadd">
      <div className="qadd-h">
        <h3><Sparkles size={15} strokeWidth={2.3} /> 빠른 입력</h3>
        <span className="qadd-sub">매물·고객 한 번에</span>
      </div>

      {!parsed && (
        <>
          <textarea className="qadd-ta" rows={4} value={text}
            placeholder={PLACEHOLDER}
            onChange={(e) => { setText(e.target.value); setErr(""); }}
            onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) run(); }} />
          <div className="qadd-row">
            {EXAMPLES.map((ex, i) => (
              <button key={i} className="qadd-ex" onClick={() => setText(ex)}>
                예시 {i === 0 ? "매물" : "손님"}
              </button>
            ))}
            <button className="qadd-go" onClick={run} disabled={busy || !text.trim()}>
              {busy ? <Loader2 size={14} className="txm-spin" /> : <Sparkles size={14} />}
              {busy ? "읽는 중…" : "읽기"}
            </button>
          </div>
          <p className="qadd-hint">
            단지·동·호를 적으면 전용면적·층·방·주차를 건축물대장에서 채웁니다.
            매물에 적힌 임대인·매도인은 고객으로도 함께 등록돼요.
          </p>
        </>
      )}

      {err && <p className="qadd-err"><AlertTriangle size={13} /> {err}</p>}
      {done && <p className="qadd-ok"><Check size={13} /> {done}</p>}

      {parsed && (
        <div className="qadd-preview">
          {(parsed.매물 || []).map((r, i) => (
            <div key={i} className={"qadd-card" + (offL.has(i) ? " off" : "")}>
              <label className="qadd-card-h">
                <input type="checkbox" checked={!offL.has(i)} onChange={() => toggle(offL, setOffL, i)} />
                <Building2 size={13} /> 매물 {i + 1}
              </label>
              <div className="qadd-fields">
                {L_FIELDS.filter(([k]) => showAll || (r[k] !== null && r[k] !== undefined && r[k] !== ""))
                  .map(([k, label, type, unit]) => (
                    <Cell key={k} label={typeof label === "function" ? label(r) : label}
                      type={type} unit={unit} value={r[k]} auto={r._auto?.[k]}
                      low={lowConf.has(k)} onChange={(v) => editL(i, k, v)} />
                  ))}
              </div>
              {!(r.type || "").trim() && (
                <div className="qadd-type">
                  <span>어떤 물건인가요?</span>
                  {QA_TYPES.map((t) => (
                    <button key={t} onClick={() => editL(i, "type", t)}>{t}</button>
                  ))}
                </div>
              )}
              {r._note && (
                <p className="qadd-note warn"><AlertTriangle size={12} /> {r._note}</p>
              )}
              {(r._complex_cands?.length || r._note) && (
                <div className="qadd-cands">
                  {(r._complex_cands || []).map((cd) => (
                    <button key={cd.complex_no} disabled={enriching !== null}
                      onClick={() => pickComplex(i, cd.complex_no)}>
                      {enriching === i ? <Loader2 size={11} className="txm-spin" /> : <Building2 size={11} />}
                      {cd.name}{cd.region ? <em>{cd.region}</em> : null}
                    </button>
                  ))}
                  <button className="ghost" onClick={() => {
                    setCxOpen(cxOpen === i ? null : i);
                    setCxQ(String(r.complex_name || "").replace(/아파트$/, "").trim());
                    setCxHits([]);
                  }}>
                    <Search size={11} /> 단지 직접 찾기
                  </button>
                </div>
              )}
              {cxOpen === i && (
                <div className="qadd-cxfind">
                  <span className="qadd-cxin">
                    <Search size={14} />
                    <input value={cxQ} autoFocus placeholder="단지명 두 글자 이상"
                      onChange={(e) => setCxQ(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter") searchComplex(); }} />
                    <button onClick={searchComplex} disabled={cxBusy || cxQ.trim().length < 2}>
                      {cxBusy ? <Loader2 size={12} className="txm-spin" /> : "찾기"}
                    </button>
                  </span>
                  {cxHits.length > 0 && (
                    <div className="qadd-cxlist">
                      {cxHits.map((h) => (
                        <button key={h.complex_no} onClick={() => pickComplex(i, h.complex_no)}>
                          <b>{h.complex_name}</b>
                          <span>{h.region}{h.households ? ` · ${h.households.toLocaleString()}세대` : ""}</span>
                        </button>
                      ))}
                    </div>
                  )}
                  {!cxBusy && cxHits.length === 0 && cxQ.trim().length >= 2 && (
                    <p className="qadd-note">찾기를 눌러 단지를 검색하세요.</p>
                  )}
                </div>
              )}
              {r._area_name_cands && r._area_name_cands.length > 1 && (
                <p className="qadd-note">평형 후보 {r._area_name_cands.join(" · ")} — 전용면적만으로는 하나로 좁혀지지 않아 비워 뒀어요.</p>
              )}
            </div>
          ))}

          {(parsed.고객 || []).map((c, i) => (
            <div key={i} className={"qadd-card" + (offC.has(i) ? " off" : "")}>
              <label className="qadd-card-h">
                <input type="checkbox" checked={!offC.has(i)} onChange={() => toggle(offC, setOffC, i)} />
                <UserRound size={13} /> {c.name || "이름 미상"} {c.phone && <span>{c.phone}</span>}
              </label>
              <div className="qadd-fields">
                <Cell label="이름" type="text" value={c.name} onChange={(v) => editC(i, "name", v)} />
                <Cell label="연락처" type="text" value={c.phone} onChange={(v) => editC(i, "phone", v)} />
                <Cell label="메모" type="text" value={c.memo} onChange={(v) => editC(i, "memo", v)} />
              </div>
              {(c.요건 || []).map((n, j) => (
                <div key={j} className="qadd-needbox">
                  <div className="qadd-needbox-h">
                    <span className={"qadd-need-t" + (n.kind === "내놓음" ? " sell" : "")}>{n.kind || "요건"}</span>
                    요건 {j + 1}
                    {typeof n.매물번호 === "number" && (
                      <span className="qadd-need-link"><Link2 size={11} /> 매물 {n.매물번호 + 1}</span>
                    )}
                  </div>
                  <div className="qadd-fields">
                    {N_FIELDS.filter(([k]) => showAll || (n[k] !== null && n[k] !== undefined && n[k] !== ""))
                      .map(([k, label, type]) => (
                        <Cell key={k} label={label} type={type} value={n[k]}
                          low={lowConf.has(`요건.${k}`)} onChange={(v) => editN(i, j, k, v)} />
                      ))}
                  </div>
                </div>
              ))}
              {(c.요건 || []).length === 0 && <p className="qadd-note">요건은 못 읽었어요. 저장 후 채우실 수 있습니다.</p>}
            </div>
          ))}

          {(parsed.확신낮음 || []).length > 0 && (
            <p className="qadd-note warn">
              <AlertTriangle size={12} /> 확인이 필요한 항목: {parsed.확신낮음!.join(" · ")}
            </p>
          )}
          {(parsed.못읽은줄 || []).length > 0 && (
            <details className="qadd-skip">
              <summary>넣지 않은 줄 {parsed.못읽은줄!.length}개</summary>
              {parsed.못읽은줄!.map((l, i) => <p key={i}>{l}</p>)}
            </details>
          )}

          <div className="qadd-row">
            <button className="qadd-ex" onClick={reset}><X size={13} /> 다시</button>
            <button className="qadd-ex" onClick={() => setShowAll((v) => !v)}>
              {showAll ? "채운 칸만" : "빈 칸까지 보기"}
            </button>
            <button className="qadd-go" onClick={save} disabled={saving}>
              {saving ? <Loader2 size={14} className="txm-spin" /> : <Check size={14} />}
              {saving ? "저장 중…"
                : `이대로 저장${[nL ? ` 매물 ${nL}` : "", nC ? ` 고객 ${nC}` : ""].join("")}`}
            </button>
          </div>
          <p className="qadd-hint">
            칸을 눌러 바로 고치실 수 있어요. 금액은 <b>24억</b>, <b>3억5천</b>처럼 적으셔도 됩니다.
            빈 칸이 있어도 저장되고, 나머지는 나중에 채우실 수 있어요.
          </p>
        </div>
      )}
    </div>
  );
}
