// 대시보드 빠른 입력 — 자연어로 치거나 문자·카톡을 붙여넣으면 매물/고객이 된다.
// 설계안 design/lounge_customer_ledger_설계안.md §2-2 §4-2 §4-3.
//
// 흐름: ① 입력 → ② 확인(자동으로 채운 값을 근거와 함께) → ③ 저장.
// 확인을 건너뛰지 않는다 — 근거 없는 값을 그냥 믿으라고 요구하지 않기 위해서다.
import { useState } from "react";
import { Sparkles, Loader2, Check, X, Building2, UserRound, Lock, AlertTriangle } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE;

type Kind = "listing" | "customer";
type Auto = Record<string, string>;
type ListingRow = Record<string, any> & { _auto?: Auto; _area_name_cands?: string[] };
type Need = Record<string, any>;
type CustomerRow = { name?: string; phone?: string; memo?: string; 요건?: Need[] };
type Parsed = {
  매물?: ListingRow[]; 고객?: CustomerRow[];
  확신낮음?: string[]; 못읽은줄?: string[];
};

const PLACEHOLDER: Record<Kind, string> = {
  listing: "고덕그라시움 142동 2004호 매매 24억 올수리 남향 즉시입주\n여러 건을 줄바꿈으로 한 번에 넣어도 됩니다",
  customer: "손님이 보낸 문자나 카톡을 그대로 붙여넣어도 됩니다\n김철수 010-1234-5678 고덕동 84 24억까지 10월 입주",
};
const EXAMPLE: Record<Kind, string> = {
  listing: "고덕그라시움 142동 2004호 매매 24억 올수리 남향 즉시입주",
  customer: "김철수 010-3001-0001 고덕동 34평 매매 24~27억 10월 입주 희망, 전세보증금 9억 9월말 반환 예정",
};

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

// 화면에 보여줄 매물 항목 — 라벨, 값 포맷
const L_FIELDS: [string, string, (v: any) => string][] = [
  ["complex_name", "단지", (v) => v],
  ["address", "주소", (v) => v],
  ["dong", "동", (v) => v],
  ["ho", "호", (v) => v],
  ["trade_type", "거래", (v) => TRADE_KOR[v] || v],
  ["price", "매매가", won],
  ["deposit", "보증금", won],
  ["rent_price", "월세", won],
  ["area2_m2", "전용", (v) => `${v}㎡ (${Math.round(v / 3.3058)}평)`],
  ["floor", "층", (v) => `${v}층`],
  ["room_cnt", "방", (v) => `${v}개`],
  ["bath_cnt", "욕실", (v) => `${v}개`],
  ["direction", "향", (v) => v],
  ["move_in", "입주", (v) => v],
  ["approve_ymd", "준공", (v) => String(v).slice(0, 4) + "년"],
  ["parking", "주차", (v) => `세대당 ${v}`],
  ["owner_name", "매도인", (v) => v],
  ["owner_tel", "연락처", (v) => v],
  ["feature_desc", "특징", (v) => v],
];

export default function QuickAdd({ authH, onSaved }: {
  authH: () => Record<string, string>; onSaved?: () => void;
}) {
  const [kind, setKind] = useState<Kind>("listing");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [parsed, setParsed] = useState<Parsed | null>(null);
  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState("");

  const reset = () => { setParsed(null); setErr(""); setDone(""); };

  const run = async () => {
    if (!text.trim() || busy) return;
    setBusy(true); setErr(""); setParsed(null); setDone("");
    try {
      const r = await fetch(`${API_BASE}/lounge/quick-parse`, {
        method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
        body: JSON.stringify({ text, kind }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j?.detail || `오류 ${r.status}`);
      setParsed(j);
    } catch (e: any) {
      setErr(e?.message || "인식에 실패했어요");
    } finally { setBusy(false); }
  };

  const save = async () => {
    if (!parsed || saving) return;
    setSaving(true); setErr("");
    try {
      if (kind === "listing") {
        const rows = parsed.매물 || [];
        for (const r of rows) {
          const body: Record<string, any> = { visibility: "office" };
          for (const [k, v] of Object.entries(r)) {
            if (!k.startsWith("_") && v !== null && v !== "") body[k] = v;
          }
          const res = await fetch(`${API_BASE}/lounge/private-listings`, {
            method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
            body: JSON.stringify(body),
          });
          if (!res.ok) throw new Error(`저장 실패 (${res.status})`);
        }
        setDone(`매물 ${rows.length}건을 매물장에 넣었어요`);
      } else {
        const res = await fetch(`${API_BASE}/lounge/customers/quick-save`, {
          method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
          body: JSON.stringify({ items: parsed.고객 || [], raw_text: text }),
        });
        const j = await res.json();
        if (!res.ok) throw new Error(j?.detail || `저장 실패 (${res.status})`);
        setDone(`고객 ${j.saved}명을 저장했어요`);
      }
      setParsed(null); setText("");
      onSaved?.();
    } catch (e: any) {
      setErr(e?.message || "저장에 실패했어요");
    } finally { setSaving(false); }
  };

  const lowConf = new Set(parsed?.확신낮음 || []);

  return (
    <div className="qadd">
      <div className="qadd-h">
        <h3><Sparkles size={15} strokeWidth={2.3} /> 빠른 입력</h3>
        <span className="qadd-seg">
          {(["listing", "customer"] as Kind[]).map((k) => (
            <button key={k} className={kind === k ? "on" : ""}
              onClick={() => { setKind(k); reset(); }}>
              {k === "listing" ? <Building2 size={13} /> : <UserRound size={13} />}
              {k === "listing" ? "매물" : "고객"}
            </button>
          ))}
        </span>
      </div>

      {!parsed && (
        <>
          <textarea className="qadd-ta" rows={3} value={text}
            placeholder={PLACEHOLDER[kind]}
            onChange={(e) => { setText(e.target.value); setErr(""); }}
            onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) run(); }} />
          <div className="qadd-row">
            <button className="qadd-ex" onClick={() => setText(EXAMPLE[kind])}>예시 넣기</button>
            <button className="qadd-go" onClick={run} disabled={busy || !text.trim()}>
              {busy ? <Loader2 size={14} className="txm-spin" /> : <Sparkles size={14} />}
              {busy ? "읽는 중…" : "읽기"}
            </button>
          </div>
          <p className="qadd-hint">
            {kind === "listing"
              ? "단지·동·호를 적으면 전용면적·층·방·주차를 건축물대장에서 채워 드려요."
              : "문자나 카톡을 그대로 붙여넣어도 됩니다. 요건이 여러 개면 나눠서 정리해요."}
          </p>
        </>
      )}

      {err && <p className="qadd-err"><AlertTriangle size={13} /> {err}</p>}
      {done && <p className="qadd-ok"><Check size={13} /> {done}</p>}

      {parsed && (
        <div className="qadd-preview">
          {kind === "listing" && (parsed.매물 || []).map((r, i) => (
            <div key={i} className="qadd-card">
              <div className="qadd-card-h">매물 {i + 1}</div>
              <div className="qadd-fields">
                {L_FIELDS.filter(([k]) => r[k] !== null && r[k] !== undefined && r[k] !== "")
                  .map(([k, label, fmt]) => {
                    const src = r._auto?.[k];
                    return (
                      <div key={k} className={"qadd-f" + (src ? " auto" : "") + (lowConf.has(k) ? " low" : "")}>
                        <span>{label}</span>
                        <b>{fmt(r[k])}</b>
                        {src && <em title={`${src}에서 자동으로 채웠어요`}><Lock size={10} /> {src}</em>}
                      </div>
                    );
                  })}
              </div>
              {r._area_name_cands && r._area_name_cands.length > 1 && (
                <p className="qadd-note">평형 후보 {r._area_name_cands.join(" · ")} — 전용면적만으로는 하나로 좁혀지지 않아 비워 뒀어요.</p>
              )}
            </div>
          ))}

          {kind === "customer" && (parsed.고객 || []).map((c, i) => (
            <div key={i} className="qadd-card">
              <div className="qadd-card-h">{c.name || "이름 미상"} {c.phone && <span>{c.phone}</span>}</div>
              {(c.요건 || []).map((n, j) => (
                <div key={j} className="qadd-need">
                  <span className={"qadd-need-t" + (n.kind === "내놓음" ? " sell" : "")}>{n.kind}</span>
                  <b>{n.trade}</b>
                  {n.role && <span className="qadd-need-r">{n.role}</span>}
                  <span className="qadd-need-p">
                    {n.ask_price ? won(n.ask_price)
                      : [won(n.budget_min), won(n.budget_max)].filter(Boolean).join(" ~ ") || "-"}
                  </span>
                  <span className="qadd-need-x">{[n.region, n.complex_name].filter(Boolean).join(" ")}</span>
                  {n.move_date && <span className="qadd-need-x">입주 {n.move_date}</span>}
                </div>
              ))}
              {(c.요건 || []).length === 0 && <p className="qadd-note">요건은 못 읽었어요. 저장 후 채우실 수 있습니다.</p>}
              {c.memo && <p className="qadd-note">{c.memo}</p>}
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
            <button className="qadd-go" onClick={save} disabled={saving}>
              {saving ? <Loader2 size={14} className="txm-spin" /> : <Check size={14} />}
              {saving ? "저장 중…" : "이대로 저장"}
            </button>
          </div>
          <p className="qadd-hint">빈 칸이 있어도 저장됩니다. 나머지는 나중에 채우실 수 있어요.</p>
        </div>
      )}
    </div>
  );
}
