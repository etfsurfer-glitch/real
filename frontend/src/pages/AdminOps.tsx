import { useCallback, useEffect, useState } from "react";
import { ClipboardList, Wallet, UserPlus, Trash2, ArrowRight, ArrowLeft, CheckCircle2, Plus } from "lucide-react";
import { useAuth } from "../auth";

const API = import.meta.env.VITE_API_BASE;
const MOTTO = "야rrrrrrr정신으로 야rrrrrrr할때까지 야rrrrrrr하자"; // 야 + r 7개씩
const CATS = ["서버비용", "홍보비", "세금", "기타"];

type Staff = { id: number; name: string; title: string };
type Task = { id: number; title: string; detail: string; assignee_id: number | null; assignee_name: string | null; assignee_title: string | null; status: string; created_at: string; updated_at: string };
type Expense = { id: number; item: string; amount: number; spender_id: number | null; spender_name: string | null; memo: string; spent_at: string | null; created_at: string; kind: string; category: string };

// UTC 문자열이 KST 기준 이번주/이번달에 드는지
function inPeriod(dt: string | null, period: string): boolean {
  if (period === "all" || !dt) return true;
  const d = new Date(dt.replace(" ", "T") + "Z");
  const k = new Date(d.getTime() + 9 * 3600 * 1000);
  const n = new Date(Date.now() + 9 * 3600 * 1000);
  if (period === "month") return k.getUTCFullYear() === n.getUTCFullYear() && k.getUTCMonth() === n.getUTCMonth();
  const sow = (x: Date) => { const day = (x.getUTCDay() + 6) % 7; const s = new Date(x); s.setUTCDate(x.getUTCDate() - day); s.setUTCHours(0, 0, 0, 0); return s; };
  return sow(k).getTime() === sow(n).getTime();
}
const won = (n: number) => n.toLocaleString() + "원";

export default function AdminOps() {
  const { token } = useAuth();
  const [tab, setTab] = useState<"work" | "expense">("work");
  const [staff, setStaff] = useState<Staff[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [err, setErr] = useState("");

  const H = useCallback((extra?: object) => ({ headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }, ...extra }), [token]);
  const load = useCallback(() => {
    if (!token || !API) return;
    Promise.all([
      fetch(`${API}/admin/ops/staff`, H()).then((r) => r.json()),
      fetch(`${API}/admin/ops/tasks`, H()).then((r) => r.json()),
      fetch(`${API}/admin/ops/expenses`, H()).then((r) => r.json()),
    ]).then(([s, t, e]) => { setStaff(s.staff || []); setTasks(t.tasks || []); setExpenses(e.expenses || []); })
      .catch((x) => setErr(String(x)));
  }, [token, H]);
  useEffect(() => { load(); }, [load]);

  return (
    <>
      <div className="ops-motto">{MOTTO}</div>
      <div className="ops-tabs">
        <button className={tab === "work" ? "on" : ""} onClick={() => setTab("work")}><ClipboardList size={15} /> 업무 워크플로우</button>
        <button className={tab === "expense" ? "on" : ""} onClick={() => setTab("expense")}><Wallet size={15} /> 비용지출</button>
      </div>
      {err && <div style={{ color: "crimson", fontSize: 13, margin: "8px 0" }}>{err}</div>}
      {tab === "work"
        ? <WorkBoard staff={staff} tasks={tasks} H={H} reload={load} />
        : <Expenses staff={staff} expenses={expenses} H={H} reload={load} />}
      <StaffManager staff={staff} H={H} reload={load} />
    </>
  );
}

// ───────── 업무 워크플로우 ─────────
function WorkBoard({ staff, tasks, H, reload }: { staff: Staff[]; tasks: Task[]; H: (e?: object) => object; reload: () => void }) {
  const [title, setTitle] = useState("");
  const [detail, setDetail] = useState("");
  const [assignee, setAssignee] = useState<string>("");
  const [period, setPeriod] = useState("month");

  const add = async () => {
    if (!title.trim()) return;
    await fetch(`${API}/admin/ops/tasks`, H({ method: "POST", body: JSON.stringify({ title, detail, assignee_id: assignee ? Number(assignee) : null, status: "todo" }) }));
    setTitle(""); setDetail(""); reload();
  };
  const move = async (t: Task, status: string) => { await fetch(`${API}/admin/ops/tasks/${t.id}`, H({ method: "PATCH", body: JSON.stringify({ status }) })); reload(); };
  const del = async (t: Task) => { if (!confirm("삭제할까요?")) return; await fetch(`${API}/admin/ops/tasks/${t.id}`, H({ method: "DELETE" })); reload(); };

  const seen = tasks.filter((t) => inPeriod(t.updated_at, period));
  const col = (s: string) => seen.filter((t) => t.status === s);
  const COLS: { key: string; label: string; color: string }[] = [
    { key: "todo", label: "할 일", color: "#6b7785" },
    { key: "doing", label: "진행 중", color: "#1268d3" },
    { key: "done", label: "완료", color: "#1f9d63" },
  ];

  return (
    <div>
      <div className="ops-form">
        <input placeholder="업무 내용" value={title} onChange={(e) => setTitle(e.target.value)} style={{ flex: "2 1 180px" }} />
        <input placeholder="상세(선택)" value={detail} onChange={(e) => setDetail(e.target.value)} style={{ flex: "2 1 160px" }} />
        <select value={assignee} onChange={(e) => setAssignee(e.target.value)} style={{ flex: "1 1 110px" }}>
          <option value="">담당자</option>
          {staff.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.title})</option>)}
        </select>
        <button className="ops-add" onClick={add}><Plus size={15} /> 등록</button>
      </div>

      <div className="ops-period">
        {[["week", "이번 주"], ["month", "이번 달"], ["all", "전체"]].map(([k, l]) => (
          <button key={k} className={period === k ? "on" : ""} onClick={() => setPeriod(k)}>{l}</button>
        ))}
      </div>

      <div className="ops-board">
        {COLS.map((c) => (
          <div key={c.key} className="ops-col">
            <div className="ops-col-h" style={{ color: c.color }}>{c.label} <span>{col(c.key).length}</span></div>
            {col(c.key).length === 0 ? <div className="ops-empty">없음</div> : col(c.key).map((t) => (
              <div key={t.id} className="ops-task">
                <div className="ops-task-t">{t.title}</div>
                {t.detail && <div className="ops-task-d">{t.detail}</div>}
                <div className="ops-task-m">
                  {t.assignee_name ? <span className="ops-who">{t.assignee_name} <em>{t.assignee_title}</em></span> : <span className="ops-who none">담당 미정</span>}
                  <span className="ops-actions">
                    {c.key !== "todo" && <button title="되돌리기" onClick={() => move(t, c.key === "done" ? "doing" : "todo")}><ArrowLeft size={13} /></button>}
                    {c.key === "todo" && <button title="진행" onClick={() => move(t, "doing")}><ArrowRight size={13} /></button>}
                    {c.key === "doing" && <button title="완료" onClick={() => move(t, "done")}><CheckCircle2 size={13} /></button>}
                    <button title="삭제" onClick={() => del(t)}><Trash2 size={13} /></button>
                  </span>
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

// ───────── 비용지출 ─────────
function Expenses({ staff, expenses, H, reload }: { staff: Staff[]; expenses: Expense[]; H: (e?: object) => object; reload: () => void }) {
  const [kind, setKind] = useState("adhoc");
  const [cat, setCat] = useState("서버비용");
  const [item, setItem] = useState("");
  const [amount, setAmount] = useState("");
  const [spender, setSpender] = useState("");
  const [date, setDate] = useState(() => new Date(Date.now() + 9 * 3600 * 1000).toISOString().slice(0, 10));
  const [memo, setMemo] = useState("");

  const add = async () => {
    const amt = parseInt(amount.replace(/[^\d-]/g, ""), 10);
    if (!amt) { alert("금액을 입력하세요"); return; }
    const label = cat === "기타" ? item.trim() : (item.trim() || cat);
    if (cat === "기타" && !label) { alert("기타 항목명을 입력하세요"); return; }
    await fetch(`${API}/admin/ops/expenses`, H({ method: "POST", body: JSON.stringify({ item: label, amount: amt, spender_id: spender ? Number(spender) : null, memo, spent_at: date, kind, category: cat }) }));
    setItem(""); setAmount(""); setMemo(""); reload();
  };
  const del = async (e: Expense) => { if (!confirm("삭제할까요?")) return; await fetch(`${API}/admin/ops/expenses/${e.id}`, H({ method: "DELETE" })); reload(); };

  // 월별 그룹
  const groups: Record<string, Expense[]> = {};
  for (const e of expenses) {
    const mk = (e.spent_at || e.created_at || "").slice(0, 7) || "기타";
    (groups[mk] ||= []).push(e);
  }
  const months = Object.keys(groups).sort().reverse();

  return (
    <div>
      <div className="ops-form">
        <select value={kind} onChange={(e) => setKind(e.target.value)} style={{ flex: "1 1 96px" }}>
          <option value="adhoc">수시지출</option>
          <option value="fixed">월 고정지출</option>
        </select>
        <select value={cat} onChange={(e) => setCat(e.target.value)} style={{ flex: "1 1 96px" }}>
          {CATS.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        {cat === "기타" && <input placeholder="항목명 직접입력" value={item} onChange={(e) => setItem(e.target.value)} style={{ flex: "1 1 110px" }} />}
        <input placeholder="금액" inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value)} style={{ flex: "1 1 90px" }} />
        <select value={spender} onChange={(e) => setSpender(e.target.value)} style={{ flex: "1 1 100px" }}>
          <option value="">담당자</option>
          {staff.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.title})</option>)}
        </select>
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} style={{ flex: "1 1 130px" }} />
        <input placeholder="메모(선택)" value={memo} onChange={(e) => setMemo(e.target.value)} style={{ flex: "1 1 110px" }} />
        <button className="ops-add" onClick={add}><Plus size={15} /> 지출등록</button>
      </div>

      {months.length === 0 ? <div className="ops-empty" style={{ marginTop: 16 }}>지출 내역이 없습니다.</div> : months.map((mk) => {
        const list = groups[mk];
        const sum = list.reduce((a, b) => a + (b.amount || 0), 0);
        return (
          <div key={mk} className="ops-month">
            <div className="ops-month-h"><b>{mk.replace("-", "년 ") + "월"}</b><span>{won(sum)}</span></div>
            <table className="ops-exp-table">
              <thead><tr><th>구분</th><th>적요</th><th>항목</th><th>담당</th><th className="num">금액</th><th>날짜</th><th></th></tr></thead>
              <tbody>
                {list.map((e) => (
                  <tr key={e.id}>
                    <td><span className="ctx-badge" style={{ background: e.kind === "fixed" ? "#eef4ff" : "#f3f4f6", color: e.kind === "fixed" ? "#1268d3" : "#666" }}>{e.kind === "fixed" ? "고정" : "수시"}</span></td>
                    <td>{e.category || "-"}</td>
                    <td>{e.item}{e.memo && <span className="ops-memo"> · {e.memo}</span>}</td>
                    <td>{e.spender_name || "-"}</td>
                    <td className="num" style={{ fontWeight: 700 }}>{won(e.amount || 0)}</td>
                    <td style={{ fontSize: 12, color: "#888" }}>{(e.spent_at || e.created_at || "").slice(0, 10)}</td>
                    <td><button className="ops-del" onClick={() => del(e)}><Trash2 size={13} /></button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}
    </div>
  );
}

// ───────── 직원 관리 ─────────
function StaffManager({ staff, H, reload }: { staff: Staff[]; H: (e?: object) => object; reload: () => void }) {
  const [name, setName] = useState("");
  const [title, setTitle] = useState("");
  const add = async () => {
    if (!name.trim()) return;
    await fetch(`${API}/admin/ops/staff`, H({ method: "POST", body: JSON.stringify({ name, title }) }));
    setName(""); setTitle(""); reload();
  };
  const del = async (s: Staff) => { if (!confirm(`${s.name} 직원을 삭제할까요?`)) return; await fetch(`${API}/admin/ops/staff/${s.id}`, H({ method: "DELETE" })); reload(); };
  return (
    <div className="ops-staff">
      <div className="section-title" style={{ marginTop: 20 }}><UserPlus size={14} /> 직원 관리</div>
      <div className="ops-form">
        <input placeholder="이름" value={name} onChange={(e) => setName(e.target.value)} style={{ flex: "1 1 120px" }} />
        <input placeholder="직함" value={title} onChange={(e) => setTitle(e.target.value)} style={{ flex: "1 1 120px" }} />
        <button className="ops-add" onClick={add}><Plus size={15} /> 직원 등록</button>
      </div>
      <div className="ops-staff-list">
        {staff.map((s) => (
          <span key={s.id} className="ops-chip">{s.name} <em>{s.title}</em><button onClick={() => del(s)} aria-label="삭제">×</button></span>
        ))}
      </div>
    </div>
  );
}
