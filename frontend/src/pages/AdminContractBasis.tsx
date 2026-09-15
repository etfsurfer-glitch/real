// 계약 기준정보 점검 대시보드 (관리자) — 법정서식·요율표·세율 등 주기 확인 대상을
// 한 화면에서 보고 '점검 완료'를 기록한다. 값 개정은 코드 배포 사안 — 여기서는
// 무엇을 언제 다시 봐야 하는지(주기·기한 경과)와 이력 관리. (2026-09-04)
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../auth";
import { Loading } from "../components/Loading";
import { ClipboardCheck, ExternalLink, AlertTriangle, CheckCircle2 } from "lucide-react";

const API = import.meta.env.VITE_API_BASE;

type BasisItem = {
  key: string; name: string; group: string; current: string; src: string;
  cycle_days: number; how: string;
  last_checked: string | null; last_note: string | null;
  due_date: string | null; overdue: boolean;
};

export default function AdminContractBasis() {
  const { token } = useAuth();
  const [items, setItems] = useState<BasisItem[] | null>(null);
  const [busyKey, setBusyKey] = useState("");
  const [noteKey, setNoteKey] = useState("");
  const [note, setNote] = useState("");

  const load = useCallback(() => {
    if (!API || !token) return;
    fetch(`${API}/admin/contract-basis`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
      .then(d => setItems(d.items || [])).catch(() => setItems([]));
  }, [token]);
  useEffect(() => { load(); }, [load]);

  const check = async (key: string) => {
    if (!token) return;
    setBusyKey(key);
    try {
      await fetch(`${API}/admin/contract-basis/check`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ key, note: noteKey === key ? note : "" }),
      });
      setNoteKey(""); setNote("");
      load();
    } finally { setBusyKey(""); }
  };

  if (!items) return <Loading />;
  const overdueN = items.filter(i => i.overdue).length;
  const groups = [...new Set(items.map(i => i.group))];

  return (
    <div style={{ maxWidth: 1000, margin: "0 auto", padding: "20px 14px 60px" }}>
      <h2 style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 19 }}>
        <ClipboardCheck size={21} /> 계약 기준정보 점검
        {overdueN > 0 && <span style={{ background: "#dc2626", color: "#fff", borderRadius: 999,
          padding: "2px 11px", fontSize: 12.5, fontWeight: 800 }}>점검 필요 {overdueN}건</span>}
      </h2>
      <p style={{ fontSize: 13, color: "var(--c-muted)", marginTop: 2 }}>
        계약서·확인설명서의 법정서식과 요율·세율 표는 개정될 수 있습니다. 주기가 지난 항목은 출처에서
        개정 여부를 확인하고 <b>점검 완료</b>를 눌러 이력을 남기세요. 개정이 발견되면 코드 갱신이 필요합니다(항목별 방법 참고).
      </p>

      {groups.map(g => (
        <div key={g}>
          <h3 style={{ fontSize: 15, margin: "22px 0 8px" }}>{g}</h3>
          {items.filter(i => i.group === g).map(it => (
            <div key={it.key} style={{ border: `1.5px solid ${it.overdue ? "#fca5a5" : "var(--c-border)"}`,
              background: it.overdue ? "#fff7f7" : "var(--c-surface)",
              borderRadius: 12, padding: "12px 16px", marginBottom: 10 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                {it.overdue
                  ? <AlertTriangle size={16} color="#dc2626" />
                  : <CheckCircle2 size={16} color="#16a34a" />}
                <b style={{ fontSize: 14.5 }}>{it.name}</b>
                <span style={{ fontSize: 12, color: "var(--c-muted)" }}>점검주기 {it.cycle_days}일</span>
                {it.src && <a href={it.src} target="_blank" rel="noreferrer"
                  style={{ display: "inline-flex", alignItems: "center", gap: 3, fontSize: 12.5 }}>
                  출처 확인 <ExternalLink size={12} /></a>}
                <span style={{ marginLeft: "auto", fontSize: 12.5,
                  color: it.overdue ? "#dc2626" : "var(--c-muted)", fontWeight: it.overdue ? 800 : 500 }}>
                  {it.last_checked
                    ? `마지막 점검 ${it.last_checked.slice(0, 10)} · 다음 기한 ${it.due_date}`
                    : "점검 이력 없음"}
                </span>
              </div>
              <div style={{ fontSize: 13, marginTop: 6 }}>현재 적용: <b>{it.current}</b></div>
              <div style={{ fontSize: 12.5, color: "var(--c-muted)", marginTop: 3 }}>개정 시: {it.how}</div>
              {it.last_note && <div style={{ fontSize: 12.5, color: "var(--c-text-soft)", marginTop: 3 }}>
                지난 메모: {it.last_note}</div>}
              <div style={{ display: "flex", gap: 8, marginTop: 9, alignItems: "center", flexWrap: "wrap" }}>
                {noteKey === it.key ? (
                  <>
                    <input value={note} onChange={e => setNote(e.target.value)} placeholder="메모(선택) — 예: 개정 없음 확인"
                      style={{ flex: 1, minWidth: 220, border: "1px solid var(--c-border)", borderRadius: 8,
                        padding: "7px 10px", fontSize: 13 }} />
                    <button onClick={() => check(it.key)} disabled={busyKey === it.key}
                      style={{ background: "var(--c-primary)", color: "#fff", border: 0, borderRadius: 8,
                        padding: "8px 16px", fontSize: 13, fontWeight: 800, cursor: "pointer" }}>
                      {busyKey === it.key ? "기록 중…" : "점검 완료 기록"}</button>
                    <button onClick={() => { setNoteKey(""); setNote(""); }}
                      style={{ background: "none", border: "1px solid var(--c-border)", borderRadius: 8,
                        padding: "8px 12px", fontSize: 13, cursor: "pointer", color: "var(--c-text)" }}>취소</button>
                  </>
                ) : (
                  <button onClick={() => { setNoteKey(it.key); setNote(""); }}
                    style={{ background: "var(--c-surface)", border: "1.5px solid var(--c-primary)",
                      color: "var(--c-primary)", borderRadius: 8, padding: "7px 16px", fontSize: 13,
                      fontWeight: 800, cursor: "pointer" }}>점검 완료</button>
                )}
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
