// 고객·요건 수정 팝업.
//
// 중개사는 칸을 채우는 사람이 아니라 말로 조건을 듣는 사람이다. 그래서
// ① 문장을 붙여넣으면 요건이 만들어지고 ② 금액은 '24억'처럼 쓰던 대로 적고
// ③ 면적은 평으로 넣게 한다(㎡ 는 우리가 바꾼다). 손이 가장 덜 가는 길로.
import { useState } from "react";
import { X, Plus, Trash2, Loader2, Check, Sparkles, UserRound, Building2,
  CalendarDays, ChevronLeft, ChevronRight, Search } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE;

export type EditNeed = {
  id?: number; kind?: string; trade?: string; role?: string;
  budget_min?: number | null; budget_max?: number | null; ask_price?: number | null;
  sigungu?: string | null; dong?: string | null; address?: string | null;
  area_min?: number | null; area_max?: number | null;
  status?: string; settle_date?: string | null; memo?: string | null;
  // 내놓음 — 특정 물건이라 동·호·전용·층이 있다(구하는 쪽은 범위를 쓴다)
  bld_dong?: string | null; ho?: string | null; area_m2?: number | null; floor_info?: string | null;
  complex_no?: string | null;
  listing_id?: number | null; _listing?: { complex_name?: string; dong?: string; ho?: string;
    area2_m2?: any; trade_type?: string } | null;
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
  // 단지 확정 — 이름만 두면 매칭이 매번 다른 단지를 찾는다('크로바'는 전국 26곳)
  const [cxOpen, setCxOpen] = useState<number | null>(null);
  const [cxQ, setCxQ] = useState("");
  const [cxHits, setCxHits] = useState<{ complex_no: string; complex_name: string; region?: string; households?: number }[]>([]);
  const [cxBusy, setCxBusy] = useState(false);
  const searchCx = async (q: string) => {
    if (q.trim().length < 2 || cxBusy) return;
    setCxBusy(true);
    try {
      const r = await fetch(`${API_BASE}/lounge/complex-search?q=${encodeURIComponent(q)}`, { headers: authH() });
      const j = await r.json();
      setCxHits(j.items ?? []);
    } catch { setCxHits([]); } finally { setCxBusy(false); }
  };

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
      const send = async (url: string, method: string, body?: any) => {
        let res: Response;
        try {
          res = await fetch(url, { method, headers: h, body: body && JSON.stringify(body) });
        } catch {
          // 네트워크 단계 실패 — 'Failed to fetch' 는 사용자에게 아무 뜻이 없다
          throw new Error("서버에 연결하지 못했어요. 잠시 후 다시 시도해 주세요.");
        }
        if (!res.ok) {
          const j = await res.json().catch(() => null);
          throw new Error(j?.detail || `저장 실패 (${res.status})`);
        }
        return res;
      };
      await send(`${API_BASE}/lounge/customers/${cust.id}`, "PATCH", { name, phone, memo });
      for (const n of needs) {
        if (n._del && n.id) {
          await send(`${API_BASE}/lounge/needs/${n.id}`, "DELETE");
          continue;
        }
        if (n._del) continue;
        const body: Record<string, any> = {};
        for (const k of ["kind", "trade", "role", "budget_min", "budget_max", "ask_price",
          "sigungu", "dong", "address", "area_min", "area_max", "status", "settle_date", "memo",
          "bld_dong", "ho", "area_m2", "floor_info", "complex_no"]) {
          body[k] = (n as any)[k] ?? null;
        }
        if (n.id) {
          await send(`${API_BASE}/lounge/needs/${n.id}`, "PUT", body);
        } else {
          await send(`${API_BASE}/lounge/needs`, "POST", { ...body, customer_id: cust.id });
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
              {/* 우선순위 — 이 고객의 요건 수만큼. 구분과 무관하게 '몇 번째 안'이다
                  (구함 1건 + 내놓음 1건이면 1안·2안이 나와야 한다) */}
              <span className="ced-pri">
                {Array.from({ length: Math.max(1, live.length) }, (_, k) => `${k + 1}안`).map((r) => (
                  <button key={r} className={roleNum(n.role) === r ? "on" : ""}
                    onClick={() => setN(i, { role: roleNum(n.role) === r ? null as any : r })}>{r}</button>
                ))}
              </span>
            </div>

            {n.listing_id && n._listing && (
              <p className="ced-linked">
                <Building2 size={12} /> 매물장에 등록된 물건입니다 —
                <b>{n._listing.complex_name}</b>
                {n._listing.dong ? ` ${n._listing.dong}` : ""}{n._listing.ho ? ` ${n._listing.ho}` : ""}
                {n._listing.area2_m2 ? ` · 전용 ${Math.round(Number(n._listing.area2_m2))}㎡` : ""}
                <em>물건 정보는 매물장에서 고치세요</em>
              </p>
            )}
            <div className="ced-grid3">
              {n.kind === "내놓음" ? (
                <>
                  {/* 내놓은 것은 특정 물건이다 — 범위가 아니라 그 집의 값이 들어간다 */}
                  <Money label="내놓은 가격" v={n.ask_price} on={(x) => setN(i, { ask_price: x })} />
                  <CxField n={n} i={i} setN={setN} open={cxOpen === i}
                    onOpen={() => { setCxOpen(cxOpen === i ? null : i); setCxQ(n.address || ""); setCxHits([]); }} />
                  <label className="ced-f"><span>지역(동)</span>
                    <input value={n.dong || ""} placeholder="고덕동"
                      onChange={(e) => setN(i, { dong: e.target.value || null })} /></label>
                  <label className="ced-f"><span>동</span>
                    <input value={n.bld_dong || ""} placeholder="104동"
                      onChange={(e) => setN(i, { bld_dong: e.target.value || null })} /></label>
                  <label className="ced-f"><span>호</span>
                    <input value={n.ho || ""} placeholder="1003호"
                      onChange={(e) => setN(i, { ho: e.target.value || null })} /></label>
                  <label className="ced-f"><span>전용</span>
                    <input value={toPy(n.area_m2)} inputMode="decimal" placeholder="34"
                      onChange={(e) => setN(i, { area_m2: fromPy(e.target.value) })} />
                    <i>평</i></label>
                  <label className="ced-f"><span>층</span>
                    <input value={n.floor_info || ""} placeholder="10/15"
                      onChange={(e) => setN(i, { floor_info: e.target.value || null })} />
                    <i>층</i></label>
                </>
              ) : (
                <>
                  <Money label="예산 최소" v={n.budget_min} on={(x) => setN(i, { budget_min: x })} />
                  <Money label="예산 최대" v={n.budget_max} on={(x) => setN(i, { budget_max: x })} />
                  <label className="ced-f"><span>지역(동)</span>
                    <input value={n.dong || ""} placeholder="고덕동"
                      onChange={(e) => setN(i, { dong: e.target.value || null })} /></label>
                  <CxField n={n} i={i} setN={setN} open={cxOpen === i}
                    onOpen={() => { setCxOpen(cxOpen === i ? null : i); setCxQ(n.address || ""); setCxHits([]); }} />
                  <label className="ced-f"><span>면적 최소</span>
                    <input value={toPy(n.area_min)} inputMode="decimal" placeholder="25"
                      onChange={(e) => setN(i, { area_min: fromPy(e.target.value) })} />
                    <i>평</i></label>
                  <label className="ced-f"><span>면적 최대</span>
                    <input value={toPy(n.area_max)} inputMode="decimal" placeholder="34"
                      onChange={(e) => setN(i, { area_max: fromPy(e.target.value) })} />
                    <i>평</i></label>
                </>
              )}
            </div>

            {cxOpen === i && (
              <div className="ced-cxfind">
                <span className="ced-cxin">
                  <Search size={14} />
                  <input value={cxQ} autoFocus placeholder="단지명 두 글자 이상"
                    onChange={(e) => setCxQ(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); searchCx(cxQ); } }} />
                  <button type="button" onClick={() => searchCx(cxQ)}
                    disabled={cxBusy || cxQ.trim().length < 2}>
                    {cxBusy ? <Loader2 size={12} className="txm-spin" /> : "찾기"}</button>
                </span>
                {cxHits.length > 0 && (
                  <div className="ced-cxlist">
                    {cxHits.map((h) => (
                      <button key={h.complex_no} type="button" onClick={() => {
                        setN(i, { address: h.complex_name, complex_no: h.complex_no });
                        setCxOpen(null); setCxHits([]);
                      }}>
                        <b>{h.complex_name}</b>
                        <span>{h.region}{h.households ? ` · ${h.households.toLocaleString()}세대` : ""}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
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

/** 단지 칸 — 이름만 두면 매칭이 흔들린다. 확정되면 자물쇠, 아니면 '단지 찾기'.
 *  이름을 직접 고치면 확정이 풀린다(다른 단지를 가리키게 되므로). */
function CxField({ n, i, setN, open, onOpen }: {
  n: EditNeed; i: number; setN: (i: number, p: Partial<EditNeed>) => void;
  open: boolean; onOpen: () => void;
}) {
  const fixed = !!n.complex_no;
  return (
    <label className={"ced-f" + (fixed ? " fixed" : "")}>
      <span>단지</span>
      <input value={n.address || ""} placeholder="고덕그라시움"
        onChange={(e) => setN(i, { address: e.target.value || null, complex_no: null })} />
      {fixed
        ? <i className="ced-cxok" title="단지가 확정됐어요"><Check size={11} /></i>
        : <button type="button" className="ced-cxbtn" title="단지 찾기"
            onClick={(e) => { e.preventDefault(); onOpen(); }}>
            <Search size={13} />{open ? "" : " 찾기"}</button>}
    </label>
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
