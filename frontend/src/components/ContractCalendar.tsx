import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Camera, Upload, CalendarDays, Trash2, ExternalLink, Download, Plus, Loader2, FileText, X, User, ShieldCheck } from "lucide-react";
import { maskSensitiveDoc } from "../lib/maskDoc";

// 계약서 → 캘린더 (관리자 가오픈)
// 계약서 사진/PDF 업로드 → AI가 일정(계약·중도금·잔금·입주·만기) 추출 →
// 확인·수정 후 자체 캘린더 저장. 일정별 '구글 캘린더 추가'(template URL) + ICS 내보내기.
const API_BASE = import.meta.env.VITE_API_BASE;

type BzEvent = {
  id: number; title: string; event_date: string; event_time: string | null;
  event_type: string; memo: string | null; contract_id: number | null;
};
type Candidate = { title: string; event_date: string; event_type: string; memo: string | null; checked?: boolean };
type Call = { phone: string; direction: string; at: string | null; duration_s: number; name: string | null };
const CALL_DIR: Record<string, { label: string; color: string }> = {
  in: { label: "수신", color: "#1f9d63" },
  out: { label: "발신", color: "#1268d3" },
  missed: { label: "부재중", color: "#d23b3b" },
};
const fmtCallPhone = (p: string) => {
  const d = (p || "").replace(/[^0-9]/g, "");
  if (d.length === 11) return `${d.slice(0, 3)}-${d.slice(3, 7)}-${d.slice(7)}`;
  if (d.length === 10) return `${d.slice(0, 3)}-${d.slice(3, 6)}-${d.slice(6)}`;
  return p;
};
const fmtCallDur = (s: number) => (!s ? "" : s >= 60 ? `${Math.floor(s / 60)}분 ${s % 60}초` : `${s}초`);
type Party = { customer_id: number | null; role: string; name: string; phone: string | null; is_company: boolean };
type Detail = {
  id: number; status: string; created_at: string; parsed: any;
  parties: Party[]; events: { id: number; title: string; event_date: string; event_type: string }[];
  doc: { exists: boolean; ext: string | null };
};
type Parsed = {
  contract_type?: string | null; doc_kind?: string | null; property_kind?: string | null;
  property_name?: string | null; property_address?: string | null;
  unit?: string | null; caution?: string | null; special_terms?: string | null;
  area?: { exclusive_m2?: number | null; supply_m2?: number | null } | null;
  lease_term?: { start?: string | null; end?: string | null; months?: number | null } | null;
  parties?: Party[] | null;
  price?: {
    sale?: number | null; deposit?: number | null; monthly_rent?: number | null;
    maintenance_fee?: number | null; down_payment?: number | null; balance?: number | null;
    premium?: number | null; interim?: { amount?: number | null; date?: string | null; note?: string | null }[] | null;
  } | null;
};

const TYPE_COLOR: Record<string, string> = {
  계약: "#1268d3", 중도금: "#b45309", 잔금: "#c0392b", 입주: "#1a7f4b", 만기: "#6b39c9", 기타: "#64748b",
};
const TYPES = ["계약", "중도금", "잔금", "입주", "만기", "기타"];

function won(v: number | null | undefined): string {
  if (!v) return "";
  if (v >= 1e8) { const e = Math.floor(v / 1e8), m = Math.round((v % 1e8) / 1e4); return m ? `${e}억 ${m.toLocaleString()}만` : `${e}억`; }
  return `${Math.round(v / 1e4).toLocaleString()}만`;
}

const ymd = (d: Date): string =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
// D-day: 오늘 기준 남은 일수(지난 일정은 회색 처리용으로 음수)
const ddayOf = (date: string, today: string): number =>
  Math.round((new Date(date + "T00:00:00").getTime() - new Date(today + "T00:00:00").getTime()) / 86400000);
const ddayText = (n: number): string => (n === 0 ? "오늘" : n > 0 ? `D-${n}` : `${-n}일 전`);

// 구글 캘린더 '일정 추가' URL (종일 일정: 종료일=다음날)
function googleCalUrl(e: BzEvent): string {
  const d = e.event_date.replace(/-/g, "");
  const next = new Date(e.event_date + "T00:00:00");
  next.setDate(next.getDate() + 1);
  const d2 = next.toISOString().slice(0, 10).replace(/-/g, "");
  const p = new URLSearchParams({
    action: "TEMPLATE",
    text: `[${e.event_type}] ${e.title}`,
    dates: e.event_time ? `${d}T${e.event_time.replace(":", "")}00/${d}T${e.event_time.replace(":", "")}00` : `${d}/${d2}`,
    details: (e.memo ? e.memo + " · " : "") + "콕집 계약 캘린더",
  });
  return `https://calendar.google.com/calendar/render?${p.toString()}`;
}

export default function ContractCalendar({ authH }: { authH: () => Record<string, string> }) {
  const [events, setEvents] = useState<BzEvent[]>([]);
  const [calls, setCalls] = useState<Call[]>([]);
  const [busy, setBusy] = useState(false);          // 업로드+인식 중
  const [err, setErr] = useState("");
  const [parsed, setParsed] = useState<Parsed | null>(null);
  const [contractId, setContractId] = useState<number | null>(null);
  const [cands, setCands] = useState<Candidate[]>([]);
  const [saving, setSaving] = useState(false);
  const [cur, setCur] = useState(() => { const n = new Date(); return { y: n.getFullYear(), m: n.getMonth() }; });
  const [selDate, setSelDate] = useState<string | null>(null);
  const [view, setView] = useState<"week" | "month" | "year">("week");   // 옆 일정 패널 범위
  const [detail, setDetail] = useState<Detail | null>(null);   // 일정 클릭 → 계약 상세
  const [docUrl, setDocUrl] = useState<string | null>(null);   // 원본(인증 필요 → blob URL)
  const [dLoading, setDLoading] = useState(false);
  const [cacheNote, setCacheNote] = useState("");   // 동일 파일 재업로드(재인식 없음) 안내
  const [maskMsg, setMaskMsg] = useState("");       // 로컬 마스킹 진행 상태
  const [maskNote, setMaskNote] = useState("");     // 마스킹 결과 안내
  const [manual, setManual] = useState(false);
  const [mTitle, setMTitle] = useState(""); const [mDate, setMDate] = useState(""); const [mType, setMType] = useState("기타");
  const fileRef = useRef<HTMLInputElement>(null);
  const camRef = useRef<HTMLInputElement>(null);

  const load = useCallback(() => {
    fetch(`${API_BASE}/biz/events`, { headers: authH() })
      .then((r) => { if (!r.ok) throw new Error(r.status === 403 ? "관리자 전용(가오픈)입니다" : `오류 ${r.status}`); return r.json(); })
      .then((d) => setEvents(d.events ?? []))
      .catch((e) => setErr(e.message));
    // 통화 내역도 캘린더에 표시 — 실패해도 일정은 정상(조용히 무시)
    fetch(`${API_BASE}/biz/calls?limit=300`, { headers: authH() })
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((d) => setCalls(d.items ?? []))
      .catch(() => { /* ignore */ });
  }, [authH]);
  useEffect(() => { load(); }, [load]);

  // 일정 → 계약 상세(계약서 사진·임대인/임차인·계약조건). 원본은 소유자 인증이 필요해 blob으로.
  const openDetail = async (cid: number) => {
    setDLoading(true); setDetail(null); setDocUrl(null);
    try {
      const r = await fetch(`${API_BASE}/biz/contracts/${cid}`, { headers: authH() });
      if (!r.ok) throw new Error("계약 정보를 불러오지 못했어요");
      const d: Detail = await r.json();
      setDetail(d);
      if (d.doc?.exists) {
        const dr = await fetch(`${API_BASE}/biz/contracts/${cid}/doc`, { headers: authH() });
        if (dr.ok) setDocUrl(URL.createObjectURL(await dr.blob()));
      }
    } catch (e) { setErr(String((e as Error).message || e)); }
    finally { setDLoading(false); }
  };
  const closeDetail = () => { if (docUrl) URL.revokeObjectURL(docUrl); setDocUrl(null); setDetail(null); };

  const onFile = async (f: File | null) => {
    if (!f || busy) return;
    setBusy(true); setErr(""); setParsed(null); setCands([]); setCacheNote(""); setMaskNote("");
    try {
      // 업로드 전 로컬(브라우저) 마스킹 — 주민·법인번호가 보이는 상태로 서버에 전송되지 않게
      const mk = await maskSensitiveDoc(f, setMaskMsg);
      setMaskNote(mk.masked > 0
        ? `주민·법인·계좌번호 ${mk.masked}곳을 이 기기에서 가린 뒤 업로드했습니다 (서버에는 가려진 파일만 저장).`
        : "");
      const fd = new FormData();
      fd.append("document", mk.file);
      setMaskMsg("AI가 계약 내용을 인식하는 중… (15~30초)");
      const ab = new AbortController();                       // 서버·네트워크가 멈춰도 3분 뒤엔 에러로 표면화
      const tm = setTimeout(() => ab.abort(), 180000);
      const r = await fetch(`${API_BASE}/biz/contracts`, { method: "POST", headers: authH(), body: fd, signal: ab.signal })
        .finally(() => clearTimeout(tm));
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof d.detail === "string" ? d.detail : "인식에 실패했어요");
      setParsed(d.parsed ?? null);
      setContractId(d.contract_id ?? null);
      setCacheNote(d.cached
        ? (d.already_confirmed
            ? "이미 등록·저장한 계약서입니다 — 기존 인식 결과를 그대로 보여드립니다(재인식 안 함). 중복 저장에 주의하세요."
            : "같은 계약서를 이미 올리신 적이 있어 기존 인식 결과를 재사용했습니다(재인식 안 함).")
        : "");
      setCands((d.candidates ?? []).map((c: Candidate) => ({ ...c, checked: true })));
      if (!(d.candidates ?? []).length) setErr("계약서에서 날짜를 찾지 못했어요. 사진이 선명한지 확인해 주세요.");
    } catch (e) {
      const msg = (e as Error).name === "AbortError"
        ? "서버 응답이 3분을 초과했습니다. 잠시 후 다시 시도해 주세요."
        : String((e as Error).message || e);
      setErr(msg);
    }
    finally {
      setBusy(false); setMaskMsg("");
      if (fileRef.current) fileRef.current.value = "";
      if (camRef.current) camRef.current.value = "";
    }
  };

  const saveCands = async () => {
    const sel = cands.filter((c) => c.checked && /^\d{4}-\d{2}-\d{2}$/.test(c.event_date) && c.title.trim());
    if (!sel.length) { setErr("저장할 일정을 선택하세요"); return; }
    setSaving(true); setErr("");
    try {
      const r = await fetch(`${API_BASE}/biz/events`, {
        method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
        body: JSON.stringify({ events: sel.map((c) => ({ ...c, contract_id: contractId })) }),
      });
      if (!r.ok) throw new Error("저장 실패");
      setParsed(null); setCands([]); setContractId(null);
      load();
    } catch (e) { setErr(String((e as Error).message || e)); }
    finally { setSaving(false); }
  };

  const addManual = async () => {
    if (!mTitle.trim() || !/^\d{4}-\d{2}-\d{2}$/.test(mDate)) return;
    const r = await fetch(`${API_BASE}/biz/events`, {
      method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
      body: JSON.stringify({ events: [{ title: mTitle.trim(), event_date: mDate, event_type: mType, memo: null }] }),
    });
    if (r.ok) { setMTitle(""); setMDate(""); setMType("기타"); setManual(false); load(); }
  };

  const del = async (id: number) => {
    if (!confirm("이 일정을 삭제할까요?")) return;
    await fetch(`${API_BASE}/biz/events/${id}`, { method: "DELETE", headers: authH() });
    load();
  };

  const downloadIcs = async () => {
    const r = await fetch(`${API_BASE}/biz/events/ics`, { headers: authH() });
    if (!r.ok) return;
    const blob = await r.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "koczip-calendar.ics";
    a.click();
    URL.revokeObjectURL(a.href);
  };

  // ── 월간 그리드 ──
  const byDate = useMemo(() => {
    const m: Record<string, BzEvent[]> = {};
    for (const e of events) (m[e.event_date] = m[e.event_date] || []).push(e);
    return m;
  }, [events]);
  const callsByDate = useMemo(() => {
    const m: Record<string, Call[]> = {};
    for (const c of calls) { const d = (c.at || "").slice(0, 10); if (d) (m[d] = m[d] || []).push(c); }
    return m;
  }, [calls]);
  const grid = useMemo(() => {
    const first = new Date(cur.y, cur.m, 1);
    const start = new Date(first); start.setDate(1 - first.getDay());
    return Array.from({ length: 42 }, (_, i) => {
      const d = new Date(start); d.setDate(start.getDate() + i);
      const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
      return { iso, day: d.getDate(), inMonth: d.getMonth() === cur.m };
    });
  }, [cur]);
  const today = new Date().toISOString().slice(0, 10);
  const selEvents = selDate ? (byDate[selDate] ?? []) : [];

  // ── 주간·월간·연간 일정 패널 ──
  // 월간·연간은 캘린더가 보고 있는 달/해와 동기(그리드 이동 시 같이 바뀜), 주간은 이번 주(일~토).
  const range = useMemo(() => {
    if (view === "week") {
      const n = new Date(today + "T00:00:00");
      const s = new Date(n); s.setDate(n.getDate() - n.getDay());
      const e = new Date(s); e.setDate(s.getDate() + 6);
      return { from: ymd(s), to: ymd(e), label: `${s.getMonth() + 1}.${s.getDate()} ~ ${e.getMonth() + 1}.${e.getDate()} (이번 주)` };
    }
    if (view === "month") {
      return { from: ymd(new Date(cur.y, cur.m, 1)), to: ymd(new Date(cur.y, cur.m + 1, 0)), label: `${cur.y}년 ${cur.m + 1}월` };
    }
    return { from: `${cur.y}-01-01`, to: `${cur.y}-12-31`, label: `${cur.y}년` };
  }, [view, cur, today]);

  const inRange = useMemo(
    () => events.filter((e) => e.event_date >= range.from && e.event_date <= range.to)
      .sort((a, b) => a.event_date.localeCompare(b.event_date) || a.event_type.localeCompare(b.event_type)),
    [events, range]);
  const summary = useMemo(() => {
    const m: Record<string, number> = {};
    for (const e of inRange) m[e.event_type] = (m[e.event_type] || 0) + 1;
    return TYPES.filter((t) => m[t]).map((t) => [t, m[t]] as [string, number]);
  }, [inRange]);
  // 연간은 목록이 길어 월별 요약으로(클릭 시 해당 월 그리드로 이동)
  const byMonth = useMemo(() => {
    const m = Array.from({ length: 12 }, () => 0);
    for (const e of inRange) m[+e.event_date.slice(5, 7) - 1]++;
    return m;
  }, [inRange]);

  return (
    <div style={{ display: "grid", gap: 14, maxWidth: 1120 }}>
      <div className="bzc-badge">관리자 가오픈 — 작업 중인 기능입니다</div>

      {/* ── 계약서 업로드 ── */}
      <div className="bzc-card">
        <div className="bzc-h"><Upload size={15} /> 계약서 등록</div>
        <p className="muted" style={{ fontSize: 12.5, margin: "2px 0 10px" }}>
          계약서 사진이나 PDF를 올리면 계약일·중도금·잔금·입주·만기 일정을 자동으로 읽어 캘린더에 넣어드립니다.
          주민등록번호·법인등록번호·계좌번호는 업로드 전에 <b>이 기기에서 자동으로 가려지며</b>, 서버에는 가려진 파일만 저장됩니다.
        </p>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input ref={fileRef} type="file" accept=".png,.jpg,.jpeg,.webp,.heic,.pdf" hidden
            onChange={(e) => onFile(e.target.files?.[0] ?? null)} />
          <input ref={camRef} type="file" accept="image/*" capture="environment" hidden
            onChange={(e) => onFile(e.target.files?.[0] ?? null)} />
          <button className="ai-send" style={{ width: "fit-content", padding: "9px 16px" }}
            disabled={busy} onClick={() => fileRef.current?.click()}>
            {busy ? <Loader2 size={14} className="spin" /> : <Upload size={14} />} 파일 선택
          </button>
          <button className="ai-send" style={{ width: "fit-content", padding: "9px 16px", background: "#1a7f4b" }}
            disabled={busy} onClick={() => camRef.current?.click()}>
            <Camera size={14} /> 사진 촬영
          </button>
        </div>
        {busy && <div className="muted" style={{ fontSize: 12.5, marginTop: 8 }}>{maskMsg || "계약서를 읽는 중입니다… (5~15초)"}</div>}
        {maskNote && (
          <div style={{ fontSize: 12, color: "#1a7f4b", background: "#f2faf5", border: "1px solid #cdeeda",
            borderRadius: 8, padding: "6px 9px", marginTop: 8, display: "flex", gap: 6, alignItems: "center" }}>
            <ShieldCheck size={13} /> {maskNote}
          </div>
        )}
        {err && <div style={{ color: "#c0392b", fontSize: 12.5, marginTop: 8 }}>{err}</div>}
      </div>

      {/* ── 인식 결과 확인 ── */}
      {parsed && cands.length > 0 && (
        <div className="bzc-card" style={{ borderColor: "#bcd7f7", background: "#f7fafe" }}>
          <div className="bzc-h"><CalendarDays size={15} /> 인식 결과 — 확인 후 저장하세요</div>
          {cacheNote && (
            <div style={{ fontSize: 12, color: "#0e6aa8", background: "#f3f9ff", border: "1px solid #d5e8fb",
              borderRadius: 8, padding: "6px 9px", marginBottom: 8 }}>♻ {cacheNote}</div>
          )}
          <div style={{ fontSize: 12.5, color: "#33425a", marginBottom: 8 }}>
            {[parsed.doc_kind || parsed.contract_type, parsed.property_name, parsed.unit,
              parsed.price?.sale ? `매매 ${won(parsed.price.sale)}` : "",
              parsed.price?.deposit ? `보증금 ${won(parsed.price.deposit)}` : "",
              parsed.price?.monthly_rent ? `월세 ${won(parsed.price.monthly_rent)}` : ""]
              .filter(Boolean).join(" · ")}
            {parsed.caution && <div style={{ color: "#b45309", marginTop: 3 }}>⚠ {parsed.caution}</div>}
          </div>

          {/* 인식된 당사자(고객) — 저장하면 고객 목록에 쌓입니다 */}
          {(parsed.parties?.length ?? 0) > 0 && (
            <div style={{ marginBottom: 8 }}>
              <div className="bzc-h" style={{ fontSize: 12.5, marginBottom: 4 }}><User size={13} /> 인식된 고객
                <span className="muted" style={{ fontWeight: 400, fontSize: 11.5 }}>— 저장 시 고객 목록에 추가됩니다</span>
              </div>
              {parsed.parties!.map((pt, i) => (
                <div key={i} className="bzc-party">
                  <span className="bzc-tag" style={{ background: pt.role === "임대인" || pt.role === "매도인" ? "#1268d3" : pt.role === "중개사" ? "#64748b" : "#1a7f4b" }}>{pt.role}</span>
                  <b style={{ fontSize: 12.5 }}>{pt.name}</b>
                  {pt.is_company && <span className="muted" style={{ fontSize: 11 }}>법인</span>}
                  {pt.phone && <span className="muted" style={{ fontSize: 11.5, marginLeft: "auto" }}>{pt.phone}</span>}
                </div>
              ))}
            </div>
          )}

          {/* 인식된 계약조건 상세 */}
          {(() => {
            const pr = parsed.price || {}, lt = parsed.lease_term || {};
            const rows: [string, string][] = [];
            if (pr.maintenance_fee) rows.push(["관리비", won(pr.maintenance_fee)]);
            if (pr.premium) rows.push(["권리금", won(pr.premium)]);
            if (pr.down_payment) rows.push(["계약금", won(pr.down_payment)]);
            if (pr.interim?.length) rows.push(["중도금", pr.interim.map((x) => `${won(x.amount)}${x.date ? ` (${x.date})` : ""}`).join(" / ")]);
            if (pr.balance) rows.push(["잔금", won(pr.balance)]);
            if (lt.start || lt.end) rows.push(["임대기간", `${lt.start ?? "?"} ~ ${lt.end ?? "?"}${lt.months ? ` (${lt.months}개월)` : ""}`]);
            if (!rows.length) return null;
            return <table className="bzc-kv" style={{ marginBottom: 8 }}><tbody>
              {rows.map(([k, v]) => <tr key={k}><th>{k}</th><td>{v}</td></tr>)}
            </tbody></table>;
          })()}
          <div style={{ display: "grid", gap: 6 }}>
            {cands.map((c, i) => (
              <div key={i} className="bzc-cand">
                <input type="checkbox" checked={!!c.checked}
                  onChange={(e) => setCands((s) => s.map((x, j) => j === i ? { ...x, checked: e.target.checked } : x))} />
                <input type="date" value={c.event_date}
                  onChange={(e) => setCands((s) => s.map((x, j) => j === i ? { ...x, event_date: e.target.value } : x))} />
                <select value={c.event_type}
                  onChange={(e) => setCands((s) => s.map((x, j) => j === i ? { ...x, event_type: e.target.value } : x))}>
                  {TYPES.map((t) => <option key={t}>{t}</option>)}
                </select>
                <input type="text" value={c.title} style={{ flex: 1, minWidth: 120 }}
                  onChange={(e) => setCands((s) => s.map((x, j) => j === i ? { ...x, title: e.target.value } : x))} />
              </div>
            ))}
          </div>
          <button className="ai-send" style={{ width: "fit-content", padding: "9px 18px", marginTop: 10 }}
            disabled={saving} onClick={saveCands}>
            {saving ? "저장 중…" : `선택한 ${cands.filter((c) => c.checked).length}건 캘린더에 저장`}
          </button>
        </div>
      )}

      {/* ── 캘린더 | 주간·월간·연간 일정 (2컬럼) ── */}
      <div className="bzc-2col">
      {/* ── 자체 캘린더 ── */}
      <div className="bzc-card">
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
          <div className="bzc-h" style={{ margin: 0 }}><CalendarDays size={15} /> 계약 캘린더</div>
          <span style={{ marginLeft: "auto", display: "inline-flex", gap: 4, alignItems: "center" }}>
            <button className="chip" onClick={() => setCur(({ y, m }) => m === 0 ? { y: y - 1, m: 11 } : { y, m: m - 1 })}>‹</button>
            <b style={{ fontSize: 14 }}>{cur.y}. {cur.m + 1}</b>
            <button className="chip" onClick={() => setCur(({ y, m }) => m === 11 ? { y: y + 1, m: 0 } : { y, m: m + 1 })}>›</button>
          </span>
        </div>
        <div className="bzc-grid">
          {["일", "월", "화", "수", "목", "금", "토"].map((d, i) => (
            <div key={d} className="bzc-dow" style={{ color: i === 0 ? "#c0392b" : i === 6 ? "#1268d3" : "#7a8aa0" }}>{d}</div>
          ))}
          {grid.map((g) => (
            <div key={g.iso}
              className={`bzc-day${g.inMonth ? "" : " out"}${g.iso === today ? " today" : ""}${g.iso === selDate ? " sel" : ""}`}
              onClick={() => setSelDate(g.iso === selDate ? null : g.iso)}>
              <span className="bzc-dn">{g.day}</span>
              {(byDate[g.iso] ?? []).slice(0, 3).map((e) => (
                <span key={e.id} className="bzc-ev" style={{ background: TYPE_COLOR[e.event_type] ?? "#64748b" }}>
                  {e.event_type}
                </span>
              ))}
              {(byDate[g.iso]?.length ?? 0) > 3 && <span className="bzc-more">+{byDate[g.iso].length - 3}</span>}
              {(callsByDate[g.iso]?.length ?? 0) > 0 && (
                <span className="bzc-callbadge" title="통화 내역">📞 {callsByDate[g.iso].length}</span>
              )}
            </div>
          ))}
        </div>

        {/* 선택한 날짜의 일정 */}
        {selDate && (
          <div style={{ marginTop: 10, borderTop: "1px solid var(--c-border)", paddingTop: 10 }}>
            <b style={{ fontSize: 13 }}>{selDate}</b>
            {selEvents.length === 0 && (callsByDate[selDate]?.length ?? 0) === 0 &&
              <div className="muted" style={{ fontSize: 12.5, marginTop: 4 }}>일정·통화가 없습니다</div>}
            {selEvents.map((e) => (
              <div key={e.id} className="bzc-evrow">
                <span className="bzc-tag" style={{ background: TYPE_COLOR[e.event_type] ?? "#64748b" }}>{e.event_type}</span>
                <span style={{ flex: 1, minWidth: 0 }}>
                  <b style={{ fontSize: 13 }}>{e.title}</b>
                  {e.memo && <span className="muted" style={{ fontSize: 12, marginLeft: 6 }}>{e.memo}</span>}
                </span>
                {e.contract_id && (
                  <button className="chip" onClick={() => openDetail(e.contract_id!)} title="계약서·당사자 보기">
                    <FileText size={12} /> 계약서
                  </button>
                )}
                <a href={googleCalUrl(e)} target="_blank" rel="noreferrer" className="chip" title="구글 캘린더에 추가">
                  <ExternalLink size={12} /> 구글
                </a>
                <button className="chip" onClick={() => del(e.id)} title="삭제"><Trash2 size={12} /></button>
              </div>
            ))}
            {(callsByDate[selDate]?.length ?? 0) > 0 && (
              <div style={{ marginTop: selEvents.length ? 8 : 4 }}>
                <div className="muted" style={{ fontSize: 11, fontWeight: 700, margin: "2px 0 4px" }}>
                  📞 통화 {callsByDate[selDate].length}건
                </div>
                {(callsByDate[selDate] ?? []).map((c, i) => {
                  const dir = CALL_DIR[c.direction] ?? CALL_DIR.in;
                  return (
                    <div key={i} className="bzc-callrow">
                      <span className="bzc-calldir" style={{ color: dir.color, borderColor: dir.color }}>{dir.label}</span>
                      <span style={{ flex: 1, minWidth: 0 }}>
                        <b style={{ fontSize: 12.5 }}>{c.name || fmtCallPhone(c.phone)}</b>
                        {c.name && <span className="muted" style={{ fontSize: 11, marginLeft: 5 }}>{fmtCallPhone(c.phone)}</span>}
                      </span>
                      <span className="muted" style={{ fontSize: 11, whiteSpace: "nowrap" }}>
                        {(c.at || "").slice(11, 16)}{c.duration_s ? ` · ${fmtCallDur(c.duration_s)}` : ""}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
          <button className="chip" onClick={() => setManual((v) => !v)}><Plus size={12} /> 일정 직접 추가</button>
          <button className="chip" onClick={downloadIcs}><Download size={12} /> ICS 내보내기 (구글·애플 캘린더 가져오기)</button>
        </div>
        {manual && (
          <div className="bzc-cand" style={{ marginTop: 8 }}>
            <input type="date" value={mDate} onChange={(e) => setMDate(e.target.value)} />
            <select value={mType} onChange={(e) => setMType(e.target.value)}>
              {TYPES.map((t) => <option key={t}>{t}</option>)}
            </select>
            <input type="text" placeholder="일정 제목 (예: 래미안 302동 잔금)" value={mTitle} style={{ flex: 1, minWidth: 140 }}
              onChange={(e) => setMTitle(e.target.value)} onKeyDown={(e) => e.key === "Enter" && addManual()} />
            <button className="ai-send" style={{ padding: "7px 14px" }} onClick={addManual}>추가</button>
          </div>
        )}
      </div>

      {/* ── 주간·월간·연간 일정 ── */}
      <div className="bzc-card">
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
          <div className="bzc-h" style={{ margin: 0 }}><CalendarDays size={15} /> 일정</div>
          <span style={{ marginLeft: "auto" }} className="bzc-seg">
            {([["week", "주간"], ["month", "월간"], ["year", "연간"]] as const).map(([k, l]) => (
              <button key={k} className={view === k ? "on" : ""} onClick={() => setView(k)}>{l}</button>
            ))}
          </span>
        </div>
        <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>{range.label} · 총 <b style={{ color: "#13294b" }}>{inRange.length}</b>건</div>

        {/* 유형별 요약 */}
        {summary.length > 0 && (
          <div style={{ display: "flex", gap: 5, flexWrap: "wrap", marginBottom: 10 }}>
            {summary.map(([t, n]) => (
              <span key={t} className="bzc-tag" style={{ background: TYPE_COLOR[t] ?? "#64748b" }}>{t} {n}</span>
            ))}
          </div>
        )}

        {inRange.length === 0 && <div className="muted" style={{ fontSize: 12.5 }}>이 기간에 일정이 없습니다</div>}

        {/* 연간은 목록이 길어 월별 요약(클릭 시 그 달로 이동) */}
        {view === "year" && inRange.length > 0 ? (
          <div className="bzc-yr">
            {byMonth.map((n, i) => (
              <button key={i} className={`bzc-yrm${n ? " has" : ""}${cur.m === i ? " on" : ""}`}
                onClick={() => { setCur({ y: cur.y, m: i }); setView("month"); }}>
                <span>{i + 1}월</span><b>{n || "-"}</b>
              </button>
            ))}
          </div>
        ) : (
          <div className="bzc-agenda">
            {inRange.map((e) => {
              const dd = ddayOf(e.event_date, today);
              return (
                <div key={e.id} className={`bzc-evrow${dd < 0 ? " past" : ""}`}>
                  <span className="bzc-tag" style={{ background: TYPE_COLOR[e.event_type] ?? "#64748b" }}>{e.event_type}</span>
                  <span style={{ flex: 1, minWidth: 0, cursor: e.contract_id ? "pointer" : "default" }}
                    onClick={() => e.contract_id && openDetail(e.contract_id)}>
                    <b style={{ fontSize: 12.5, textDecoration: e.contract_id ? "underline dotted" : "none" }}>{e.title}</b>
                    <span className="muted" style={{ fontSize: 11.5, marginLeft: 6 }}>
                      {e.event_date.slice(5).replace("-", ".")}{e.event_time ? ` ${e.event_time}` : ""}
                    </span>
                  </span>
                  <span className="bzc-dday" style={{ color: dd === 0 ? "#c0392b" : dd > 0 && dd <= 7 ? "#b45309" : "#7a8aa0" }}>
                    {ddayText(dd)}
                  </span>
                  <a href={googleCalUrl(e)} target="_blank" rel="noreferrer" className="chip" title="구글 캘린더에 추가">
                    <ExternalLink size={12} />
                  </a>
                </div>
              );
            })}
          </div>
        )}
      </div>
      </div>

      {/* ── 계약 상세: 계약서 사진 + 임대인/임차인 + 계약조건 ── */}
      {(detail || dLoading) && (
        <div className="bzc-modal" onClick={closeDetail}>
          <div className="bzc-modal-in" onClick={(ev) => ev.stopPropagation()}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
              <div className="bzc-h" style={{ margin: 0 }}><FileText size={15} /> 계약 상세</div>
              <button className="chip" style={{ marginLeft: "auto" }} onClick={closeDetail}><X size={13} /></button>
            </div>
            {dLoading && <div className="muted" style={{ fontSize: 12.5 }}>불러오는 중…</div>}
            {detail && (() => {
              const p = detail.parsed || {}, pr = p.price || {}, lt = p.lease_term || {};
              const rows: [string, string][] = [];
              if (p.contract_type || p.doc_kind) rows.push(["계약 종류", [p.contract_type, p.doc_kind].filter(Boolean).join(" · ")]);
              if (p.property_name || p.property_address) rows.push(["물건", [p.property_name, p.unit, p.property_address].filter(Boolean).join(" ")]);
              if (pr.sale) rows.push(["매매대금", won(pr.sale)]);
              if (pr.deposit) rows.push(["보증금", won(pr.deposit)]);
              if (pr.monthly_rent) rows.push(["월세", won(pr.monthly_rent)]);
              if (pr.maintenance_fee) rows.push(["관리비", won(pr.maintenance_fee)]);
              if (pr.premium) rows.push(["권리금", won(pr.premium)]);
              if (pr.down_payment) rows.push(["계약금", won(pr.down_payment)]);
              if (Array.isArray(pr.interim) && pr.interim.length)
                rows.push(["중도금", pr.interim.map((x: any) => `${won(x.amount)}${x.date ? ` (${x.date})` : ""}${x.note ? ` ${x.note}` : ""}`).join(" / ")]);
              if (pr.balance) rows.push(["잔금", won(pr.balance)]);
              if (lt.start || lt.end) rows.push(["임대기간", `${lt.start ?? "?"} ~ ${lt.end ?? "?"}${lt.months ? ` (${lt.months}개월)` : ""}`]);
              const ar = p.area || {};
              if (ar.exclusive_m2 || ar.supply_m2) rows.push(["면적", [ar.supply_m2 && `공급 ${ar.supply_m2}㎡`, ar.exclusive_m2 && `전용 ${ar.exclusive_m2}㎡`].filter(Boolean).join(" · ")]);
              return (
                <div className="bzc-detail">
                  <div>
                    {/* 당사자 */}
                    <div className="bzc-h" style={{ fontSize: 13 }}><User size={13} /> 당사자</div>
                    {detail.parties.length === 0 && <div className="muted" style={{ fontSize: 12 }}>추출된 당사자가 없습니다</div>}
                    {detail.parties.map((pt, i) => (
                      <div key={i} className="bzc-party">
                        <span className="bzc-tag" style={{ background: pt.role === "임대인" || pt.role === "매도인" ? "#1268d3" : pt.role === "중개사" ? "#64748b" : "#1a7f4b" }}>{pt.role}</span>
                        <b style={{ fontSize: 12.5 }}>{pt.name}</b>
                        {pt.is_company && <span className="muted" style={{ fontSize: 11 }}>법인</span>}
                        {pt.phone && <a href={`tel:${pt.phone}`} className="muted" style={{ fontSize: 11.5, marginLeft: "auto" }}>{pt.phone}</a>}
                      </div>
                    ))}
                    {/* 계약조건 */}
                    <div className="bzc-h" style={{ fontSize: 13, marginTop: 12 }}>계약 조건</div>
                    <table className="bzc-kv"><tbody>
                      {rows.map(([k, v]) => <tr key={k}><th>{k}</th><td>{v}</td></tr>)}
                    </tbody></table>
                    {p.special_terms && (
                      <div style={{ marginTop: 8 }}>
                        <div className="bzc-h" style={{ fontSize: 13 }}>특약</div>
                        <div style={{ fontSize: 12, color: "#33425a", lineHeight: 1.5 }}>{p.special_terms}</div>
                      </div>
                    )}
                    {p.caution && <div style={{ color: "#b45309", fontSize: 12, marginTop: 8 }}>⚠ {p.caution}</div>}
                    {/* 관련 일정 */}
                    {detail.events.length > 0 && (
                      <>
                        <div className="bzc-h" style={{ fontSize: 13, marginTop: 12 }}>관련 일정</div>
                        {detail.events.map((e) => (
                          <div key={e.id} className="bzc-evrow">
                            <span className="bzc-tag" style={{ background: TYPE_COLOR[e.event_type] ?? "#64748b" }}>{e.event_type}</span>
                            <span style={{ flex: 1, fontSize: 12.5 }}>{e.title}</span>
                            <span className="muted" style={{ fontSize: 11.5 }}>{e.event_date}</span>
                          </div>
                        ))}
                      </>
                    )}
                  </div>
                  {/* 계약서 원본 */}
                  <div>
                    <div className="bzc-h" style={{ fontSize: 13 }}>계약서 원본</div>
                    {!detail.doc.exists && <div className="muted" style={{ fontSize: 12 }}>원본이 없습니다</div>}
                    {docUrl && (detail.doc.ext === ".pdf"
                      ? <iframe src={docUrl} className="bzc-doc" title="계약서" />
                      : <img src={docUrl} className="bzc-doc" alt="계약서" />)}
                    {detail.doc.exists && !docUrl && <div className="muted" style={{ fontSize: 12 }}>불러오는 중…</div>}
                    {docUrl && <a href={docUrl} download={`계약서_${detail.id}${detail.doc.ext ?? ""}`} className="chip" style={{ marginTop: 6 }}><Download size={12} /> 원본 저장</a>}
                  </div>
                </div>
              );
            })()}
          </div>
        </div>
      )}

      <p className="muted" style={{ fontSize: 11.5 }}>
        계약서 원본은 서버에 안전하게 보관되며 외부에 공개되지 않습니다. AI 인식 결과는 초안이므로 반드시 원본과
        대조해 확인하세요. ‘구글’ 버튼은 구글 캘린더 등록 화면을 열어줍니다(구글 로그인 필요).
      </p>
    </div>
  );
}
