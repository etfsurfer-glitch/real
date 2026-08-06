// 고객·요건 수정 팝업.
//
// 중개사는 칸을 채우는 사람이 아니라 말로 조건을 듣는 사람이다. 그래서
// ① 문장을 붙여넣으면 요건이 만들어지고 ② 금액은 '24억'처럼 쓰던 대로 적고
// ③ 면적은 평으로 넣게 한다(㎡ 는 우리가 바꾼다). 손이 가장 덜 가는 길로.
import { useState } from "react";
import { X, Plus, Trash2, Loader2, Check, Sparkles, UserRound, Building2,
  CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE;

export type EditNeed = {
  id?: number; kind?: string; trade?: string; role?: string;
  budget_min?: number | null; budget_max?: number | null; ask_price?: number | null;
  sigungu?: string | null; dong?: string | null; address?: string | null;
  area_min?: number | null; area_max?: number | null;
  status?: string; settle_date?: string | null; memo?: string | null;
  _new?: boolean; _del?: boolean;
};
export type EditCustomer = {
  id: number; name?: string; phone?: string; memo?: string; needs: EditNeed[];
};

const KINDS = ["구함", "내놓음"];
const TRADES: [string, string][] = [["A1", "매매"], ["B1", "전세"], ["B2", "월세"]];
const STATUS = ["탐색", "비교", "협상", "계약", "완료", "보류"];
const SETTLE_QUICK = ["즉시", "협의"];
// 예전 값(주안·대안·보유)을 우선순위로 읽는다 — 기존 요건도 버튼이 켜져 보이게
const ROLE_OLD: Record<string, string> = { 주안: "1안", 대안: "2안", 보유: "1안" };
const roleNum = (r?: string | null) => ROLE_OLD[r || ""] || r || "";

/** '24억' '3억5천' '1,000만' → 원. 숫자만 있으면 억으로 본다(중개사는 억으로 말한다). */
export function parseMoney(raw: string): number | null {
  const t = (raw || "").replace(/[\s,]/g, "");
  if (!t) return null;
  if (/^\d+(\.\d+)?$/.test(t)) return Math.round(parseFloat(t) * 1e8);
  let v = 0, hit = false;
  const e = t.match(/(\d+(?:\.\d+)?)억/);
  if (e) { v += parseFloat(e[1]) * 1e8; hit = true; }
  const ch = t.match(/억(\d+(?:\.\d+)?)천/) || (!e && t.match(/(\d+(?:\.\d+)?)천/));
  if (ch) { v += parseFloat(ch[1]) * 1e7; hit = true; }
  const m = t.match(/(\d+(?:\.\d+)?)만/);
  if (m && !ch) { v += parseFloat(m[1]) * 1e4; hit = true; }
  else if (e && !ch) {
    const rest = t.slice(t.indexOf("억") + 1).match(/^(\d+)$/);
    if (rest) { v += Number(rest[1]) * 1e4; hit = true; }
  }
  return hit ? Math.round(v) : null;
}
export function moneyText(won?: number | null): string {
  if (!won) return "";
  const e = Math.floor(won / 1e8), m = Math.round((won % 1e8) / 1e4);
  if (e) return m ? `${e}억 ${m.toLocaleString()}` : `${e}억`;
  return `${Math.round(won / 1e4).toLocaleString()}만`;
}
const toPy = (m2?: number | null) => (m2 ? String(Math.round(Number(m2) / 3.3058)) : "");
const fromPy = (py: string) => {
  const v = parseFloat((py || "").replace(/[^\d.]/g, ""));
  return isNaN(v) || !v ? null : Math.round(v * 3.3058 * 10) / 10;
};

/** 잔금시기 달력 — 날짜까지 잡힌 건 일로, 아직 '10월쯤'이면 월로 고른다.
 *  둘 다 실제로 쓰이므로 한 달력 안에서 둘 다 되게 한다. */
function SettlePicker({ value, onPick, onClose }: {
  value?: string | null; onPick: (v: string) => void; onClose: () => void;
}) {
  const base = (() => {
    const m = (value || "").match(/(\d{4})-(\d{2})/);
    if (m) return { y: +m[1], m: +m[2] - 1 };
    const n = new Date();
    return { y: n.getFullYear(), m: n.getMonth() };
  })();
  const [cur, setCur] = useState(base);
  const pad = (v: number) => String(v).padStart(2, "0");
  const grid = (() => {
    const first = new Date(cur.y, cur.m, 1);
    const start = new Date(first);
    start.setDate(1 - first.getDay());
    return Array.from({ length: 42 }, (_, i) => {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      return { d, iso: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`,
        inM: d.getMonth() === cur.m };
    });
  })();
  const today = new Date();
  const todayIso = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;
  const monthIso = `${cur.y}-${pad(cur.m + 1)}`;
  return (
    <div className="ced-cal" onClick={(e) => e.stopPropagation()}>
      <div className="ced-cal-h">
        <button onClick={() => setCur((c) => {
          const d = new Date(c.y, c.m - 1, 1); return { y: d.getFullYear(), m: d.getMonth() };
        })} aria-label="이전"><ChevronLeft size={15} /></button>
        {/* 헤더를 누르면 '그 달 전체'로 잡힌다 — 날짜가 아직 안 정해진 손님이 대부분이다 */}
        <button className="ced-cal-m" onClick={() => { onPick(monthIso); onClose(); }}>
          {cur.y}년 {cur.m + 1}월 <em>이 달로</em>
        </button>
        <button onClick={() => setCur((c) => {
          const d = new Date(c.y, c.m + 1, 1); return { y: d.getFullYear(), m: d.getMonth() };
        })} aria-label="다음"><ChevronRight size={15} /></button>
      </div>
      <div className="ced-cal-g">
        {["일", "월", "화", "수", "목", "금", "토"].map((w, i) => (
          <span key={w} className={"dw" + (i === 0 ? " sun" : i === 6 ? " sat" : "")}>{w}</span>
        ))}
        {grid.map((g) => (
          <button key={g.iso}
            className={"dd" + (g.inM ? "" : " out") + (g.iso === todayIso ? " today" : "")
              + (g.iso === value ? " on" : "")}
            onClick={() => { onPick(g.iso); onClose(); }}>{g.d.getDate()}</button>
        ))}
      </div>
      <div className="ced-cal-f">
        {SETTLE_QUICK.map((q) => (
          <button key={q} onClick={() => { onPick(q); onClose(); }}>{q}</button>
        ))}
        <button className="clr" onClick={() => { onPick(""); onClose(); }}>지우기</button>
      </div>
    </div>
  );
}


export default function CustomerEdit({ authH, cust, onClose, onSaved }: {
  authH: () => Record<string, string>; cust: EditCustomer;
  onClose: () => void; onSaved: () => void;
}) {
  const [name, setName] = useState(cust.name || "");
  const [phone, setPhone] = useState(cust.phone || "");
  const [memo, setMemo] = useState(cust.memo || "");
  const [needs, setNeeds] = useState<EditNeed[]>(cust.needs.map((n) => ({ ...n })));
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const [paste, setPaste] = useState("");
  const [parsing, setParsing] = useState(false);
  const [calOpen, setCalOpen] = useState<number | null>(null);   // 달력을 연 요건

  const setN = (i: number, patch: Partial<EditNeed>) =>
    setNeeds((ns) => ns.map((n, j) => (i === j ? { ...n, ...patch } : n)));
  const addNeed = () =>
    setNeeds((ns) => [...ns, { kind: "구함", trade: "A1", status: "탐색", _new: true }]);
  const delNeed = (i: number) =>
    setNeeds((ns) => ns.map((n, j) => (i === j ? { ...n, _del: true } : n)).filter((n) => !(n._del && n._new)));

  // 문장 붙여넣기 → 요건 자동 생성. 칸을 채우는 것보다 이게 빠르다.
  const runPaste = async () => {
    if (paste.trim().length < 2 || parsing) return;
    setParsing(true); setErr("");
    try {
      const r = await fetch(`${API_BASE}/lounge/needs/parse`, {
        method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
        body: JSON.stringify({ text: paste }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j?.detail || `오류 ${r.status}`);
      const got: EditNeed[] = (j.needs || []).map((n: any) => ({
        kind: n.kind || "구함", trade: n.trade || "A1", role: roleNum(n.role),
        budget_min: n.budget_min ?? null, budget_max: n.budget_max ?? null,
        ask_price: n.ask_price ?? null, dong: n.region || null, address: n.complex_name || null,
        area_min: n.area_min ?? null, area_max: n.area_max ?? null,
        settle_date: n.settle_date || null, status: "탐색", _new: true,
      }));
      if (!got.length) { setErr("요건을 못 읽었어요. 조금 더 자세히 적어 주세요."); return; }
      setNeeds((ns) => [...ns, ...got]);
      setPaste("");
    } catch (e: any) {
      setErr(e?.message || "인식에 실패했어요");
    } finally { setParsing(false); }
  };

  const save = async () => {
    if (!name.trim()) { setErr("이름을 적어 주세요"); return; }
    setSaving(true); setErr("");
    try {
      const h = { ...authH(), "Content-Type": "application/json" };
      await fetch(`${API_BASE}/lounge/customers/${cust.id}`, {
        method: "PATCH", headers: h, body: JSON.stringify({ name, phone, memo }),
      }).then((r) => { if (!r.ok) throw new Error("고객 저장 실패"); });
      for (const n of needs) {
        if (n._del && n.id) {
          await fetch(`${API_BASE}/lounge/needs/${n.id}`, { method: "DELETE", headers: h });
          continue;
        }
        if (n._del) continue;
        const body: Record<string, any> = {};
        for (const k of ["kind", "trade", "role", "budget_min", "budget_max", "ask_price",
          "sigungu", "dong", "address", "area_min", "area_max", "status", "settle_date", "memo"]) {
          body[k] = (n as any)[k] ?? null;
        }
        if (n.id) {
          await fetch(`${API_BASE}/lounge/needs/${n.id}`, { method: "PUT", headers: h, body: JSON.stringify(body) });
        } else {
          await fetch(`${API_BASE}/lounge/needs`, {
            method: "POST", headers: h, body: JSON.stringify({ ...body, customer_id: cust.id }),
          });
        }
      }
      onSaved(); onClose();
    } catch (e: any) {
      setErr(e?.message || "저장에 실패했어요");
    } finally { setSaving(false); }
  };

  const live = needs.filter((n) => !n._del);

  return (
    <div className="ced-ov" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="ced">
        <button className="ced-x" onClick={onClose} aria-label="닫기"><X size={18} /></button>
        <h3 className="ced-t"><UserRound size={16} /> 고객 정보 수정</h3>

        <div className="ced-grid3">
          <label className="ced-f"><span>이름</span>
            <input value={name} onChange={(e) => setName(e.target.value)} autoFocus /></label>
          <label className="ced-f"><span>연락처</span>
            <input value={phone} inputMode="tel" placeholder="010-0000-0000"
              onChange={(e) => setPhone(e.target.value)} /></label>
          <label className="ced-f"><span>메모</span>
            <input value={memo} placeholder="소개 경로·특이사항"
              onChange={(e) => setMemo(e.target.value)} /></label>
        </div>

        <div className="ced-sec">
          <h4><Building2 size={13} /> 요건 {live.length}건</h4>
          <button className="ced-add" onClick={addNeed}><Plus size={13} /> 빈 요건 추가</button>
        </div>

        <div className="ced-paste">
          <Sparkles size={14} />
          <input value={paste} placeholder="문장으로 넣기 — 예: 고덕동 34평 매매 24~27억 10월 잔금"
            onChange={(e) => setPaste(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") runPaste(); }} />
          <button onClick={runPaste} disabled={parsing || paste.trim().length < 2}>
            {parsing ? <Loader2 size={13} className="txm-spin" /> : "읽기"}
          </button>
        </div>

        {live.length === 0 && <p className="ced-empty">요건이 없습니다. 위에서 문장으로 넣거나 빈 요건을 추가하세요.</p>}

        {needs.map((n, i) => n._del ? null : (
          <div key={n.id ?? `new${i}`} className="ced-need">
            <div className="ced-need-h">
              <span className={"ced-kind" + (n.kind === "내놓음" ? " sell" : "")}>{n.kind}</span>
              {n._new && <em>새 요건</em>}
              <button className="ced-del" onClick={() => delNeed(i)} aria-label="삭제">
                <Trash2 size={13} />
              </button>
            </div>

            <div className="ced-chips">
              {KINDS.map((k) => (
                <button key={k} className={n.kind === k ? "on" : ""}
                  onClick={() => setN(i, { kind: k })}>{k}</button>
              ))}
              <i />
              {TRADES.map(([v, l]) => (
                <button key={v} className={n.trade === v ? "on" : ""}
                  onClick={() => setN(i, { trade: v })}>{l}</button>
              ))}
              <i />
              {/* 우선순위 — 같은 구분(구함·내놓음) 요건 수만큼. '2안이 뭐였죠'가 바로 보인다 */}
              <span className="ced-pri">
                {Array.from({ length: Math.max(1, live.filter((x) => x.kind === n.kind).length) },
                  (_, k) => `${k + 1}안`).map((r) => (
                    <button key={r} className={roleNum(n.role) === r ? "on" : ""}
                      onClick={() => setN(i, { role: roleNum(n.role) === r ? null as any : r })}>{r}</button>
                  ))}
              </span>
            </div>

            <div className="ced-grid3">
              {n.kind === "내놓음" ? (
                <Money label="내놓은 가격" v={n.ask_price} on={(x) => setN(i, { ask_price: x })} />
              ) : (
                <>
                  <Money label="예산 최소" v={n.budget_min} on={(x) => setN(i, { budget_min: x })} />
                  <Money label="예산 최대" v={n.budget_max} on={(x) => setN(i, { budget_max: x })} />
                </>
              )}
              <label className="ced-f"><span>지역(동)</span>
                <input value={n.dong || ""} placeholder="고덕동"
                  onChange={(e) => setN(i, { dong: e.target.value || null })} /></label>
              <label className="ced-f"><span>단지·주소</span>
                <input value={n.address || ""} placeholder="고덕그라시움"
                  onChange={(e) => setN(i, { address: e.target.value || null })} /></label>
              <label className="ced-f"><span>면적 최소</span>
                <input value={toPy(n.area_min)} inputMode="decimal" placeholder="25"
                  onChange={(e) => setN(i, { area_min: fromPy(e.target.value) })} />
                <i>평</i></label>
              <label className="ced-f"><span>면적 최대</span>
                <input value={toPy(n.area_max)} inputMode="decimal" placeholder="34"
                  onChange={(e) => setN(i, { area_max: fromPy(e.target.value) })} />
                <i>평</i></label>
            </div>

            <div className="ced-row2">
              <label className="ced-f wide"><span>잔금시기</span>
                <input value={n.settle_date || ""} placeholder="달력에서 고르거나 직접 입력"
                  onChange={(e) => setN(i, { settle_date: e.target.value || null })} />
                <button type="button" className="ced-calbtn"
                  onClick={(e) => { e.preventDefault(); setCalOpen(calOpen === i ? null : i); }}
                  aria-label="달력">
                  <CalendarDays size={14} />
                </button>
              </label>
              {calOpen === i && (
                <SettlePicker value={n.settle_date}
                  onPick={(v) => setN(i, { settle_date: v || null })}
                  onClose={() => setCalOpen(null)} />
              )}
            </div>

            <div className="ced-row2">
              <span className="ced-quick lbl">진행
                {STATUS.map((st) => (
                  <button key={st} className={n.status === st ? "on" : ""}
                    onClick={() => setN(i, { status: st })}>{st}</button>
                ))}
              </span>
            </div>
          </div>
        ))}

        {err && <p className="ced-err">{err}</p>}
        <div className="ced-foot">
          <button className="ced-cancel" onClick={onClose}>취소</button>
          <button className="ced-save" onClick={save} disabled={saving}>
            {saving ? <Loader2 size={14} className="txm-spin" /> : <Check size={14} />}
            {saving ? "저장 중…" : "저장"}
          </button>
        </div>
      </div>
    </div>
  );
}

/** 금액 칸 — 쓰던 대로 '24억' 적으면 되고, 옆에 해석된 값이 뜬다. */
function Money({ label, v, on }: { label: string; v?: number | null; on: (x: number | null) => void }) {
  const [draft, setDraft] = useState<string | null>(null);
  const shown = draft !== null ? draft : moneyText(v);
  return (
    <label className="ced-f"><span>{label}</span>
      <input value={shown} inputMode="decimal" placeholder="24억"
        onChange={(e) => setDraft(e.target.value)}
        onBlur={(e) => { on(parseMoney(e.target.value)); setDraft(null); }}
        onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }} />
      {draft !== null && parseMoney(draft) != null && <i>{moneyText(parseMoney(draft))}</i>}
    </label>
  );
}
