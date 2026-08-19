import { useCallback, useEffect, useState } from "react";
import { Gift, Coffee, Candy, Wallet, RefreshCw, AlertTriangle } from "lucide-react";
import { useAuth } from "../auth";

const API = import.meta.env.VITE_API_BASE;

type Balance = { ok: boolean; balance: number | null; code?: string; message?: string };
type SummRow = { kind: string; status: string; n: number };
type Coupon = {
  id: number; kind: string; source: string; status: string;
  created_at: string; used_at: string | null; member_no: number | null; phone: string | null;
};

const KIND = { coffee: "메가커피", lollipop: "추파춥스" } as Record<string, string>;
const ST = { issued: "발급완료", pending: "대기", used: "사용" } as Record<string, string>;

function won(n: number | null | undefined) {
  return n == null ? "—" : `₩${n.toLocaleString()}`;
}
function when(s: string) {
  const t = new Date(s.replace(" ", "T"));
  if (isNaN(t.getTime())) return s.slice(5, 16);
  return `${t.getMonth() + 1}/${t.getDate()} ${String(t.getHours()).padStart(2, "0")}:${String(t.getMinutes()).padStart(2, "0")}`;
}

export default function AdminEvent() {
  const { token } = useAuth();
  const [bal, setBal] = useState<Balance | null>(null);
  const [summary, setSummary] = useState<SummRow[] | null>(null);
  const [items, setItems] = useState<Coupon[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const load = useCallback(() => {
    if (!token || !API) return;
    fetch(`${API}/admin/giftishow/balance`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json()).then(setBal).catch(() => setBal(null));
    fetch(`${API}/admin/event/coupons`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json()).then((d) => { setSummary(d.summary || []); setItems(d.items || []); })
      .catch(() => { setSummary([]); setItems([]); });
  }, [token]);
  useEffect(() => { load(); }, [load]);

  const cnt = (kind: string, status?: string) =>
    (summary || []).filter((s) => s.kind === kind && (!status || s.status === status))
      .reduce((a, s) => a + s.n, 0);
  const pending = (summary || []).filter((s) => s.status === "pending").reduce((a, s) => a + s.n, 0);

  const flush = async () => {
    setBusy(true); setMsg("");
    try {
      const r = await fetch(`${API}/admin/giftishow/flush`, {
        method: "POST", headers: { Authorization: `Bearer ${token}` },
      });
      const d = await r.json();
      setMsg(`대기 ${d.pending}건 중 ${d.issued}건 재발급 완료`);
      load();
    } catch { setMsg("재시도 실패"); }
    finally { setBusy(false); window.setTimeout(() => setMsg(""), 5000); }
  };

  const lowBal = bal?.balance != null && bal.balance < 5000;

  return (
    <div className="aev">
      <h2 className="aev-h"><Gift size={19} strokeWidth={2.3} aria-hidden /> 이벤트 경품 · 비즈머니</h2>

      <div className="aev-cards">
        <div className={`aev-card bal${lowBal ? " low" : ""}`}>
          <div className="aev-card-t"><Wallet size={15} strokeWidth={2.3} /> 기프티쇼 비즈머니</div>
          <div className="aev-bal">{bal ? won(bal.balance) : "…"}</div>
          <div className="aev-card-s">
            {bal && !bal.ok ? <span className="aev-err">조회 실패 {bal.code}</span>
              : lowBal ? <span className="aev-err">잔액 부족 — 충전 필요</span> : "발급 가능 잔액"}
          </div>
        </div>
        <div className="aev-card">
          <div className="aev-card-t"><Coffee size={15} strokeWidth={2.3} /> 커피 지급</div>
          <div className="aev-num">{cnt("coffee", "issued").toLocaleString()}<em>건</em></div>
          <div className="aev-card-s">대기 {cnt("coffee", "pending")} · 사용 {cnt("coffee", "used")}</div>
        </div>
        <div className="aev-card">
          <div className="aev-card-t"><Candy size={15} strokeWidth={2.3} /> 추파춥스 지급</div>
          <div className="aev-num">{cnt("lollipop", "issued").toLocaleString()}<em>건</em></div>
          <div className="aev-card-s">대기 {cnt("lollipop", "pending")} · 사용 {cnt("lollipop", "used")}</div>
        </div>
      </div>

      {pending > 0 && (
        <div className="aev-pending">
          <AlertTriangle size={15} strokeWidth={2.3} />
          발급 대기 <b>{pending}건</b>이 있어요(잔액 부족·전화 미인증 등). 충전 후 재시도하세요.
          <button className="aev-flush" onClick={flush} disabled={busy}>
            <RefreshCw size={13} strokeWidth={2.4} /> {busy ? "재시도 중…" : "대기분 재발급"}
          </button>
        </div>
      )}
      {msg && <div className="aev-msg">{msg}</div>}

      <div className="aev-tablewrap">
        <table className="aev-table">
          <thead>
            <tr><th>#</th><th>종류</th><th>미션</th><th>상태</th><th>회원번호</th><th>전화</th><th>발급시각</th></tr>
          </thead>
          <tbody>
            {items === null ? (
              <tr><td colSpan={7} className="aev-empty">불러오는 중…</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={7} className="aev-empty">아직 지급된 경품이 없어요.</td></tr>
            ) : items.map((c) => (
              <tr key={c.id}>
                <td>{c.id}</td>
                <td><span className={`aev-kind ${c.kind}`}>{KIND[c.kind] || c.kind}</span></td>
                <td>{c.source}</td>
                <td><span className={`aev-st ${c.status}`}>{ST[c.status] || c.status}</span></td>
                <td>{c.member_no ?? "—"}</td>
                <td className="aev-phone">{c.phone || "—"}</td>
                <td>{when(c.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <style>{`
.aev{max-width:920px;margin:0 auto;padding:18px 14px 80px}
.aev-h{display:flex;align-items:center;gap:8px;font-size:20px;font-weight:800;color:var(--c-text,#18233a);margin:0 0 16px}
.aev-cards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px}
@media(max-width:640px){.aev-cards{grid-template-columns:1fr}}
.aev-card{background:var(--c-surface,#fff);border:1px solid var(--c-border,#e3e8ef);border-radius:15px;padding:16px 18px}
.aev-card.bal{background:#f3f8ff;border-color:#cfe0f7}
.aev-card.bal.low{background:#fdf2f2;border-color:#f2c9c4}
.aev-card-t{display:flex;align-items:center;gap:6px;font-size:12.5px;font-weight:800;color:var(--c-text-soft,#5a6b80)}
.aev-bal{font-size:30px;font-weight:800;color:#1268d3;margin:8px 0 4px;font-variant-numeric:tabular-nums}
.aev-card.bal.low .aev-bal{color:#c0392b}
.aev-num{font-size:30px;font-weight:800;color:var(--c-text,#18233a);margin:8px 0 4px;font-variant-numeric:tabular-nums}
.aev-num em{font-style:normal;font-size:15px;font-weight:700;color:var(--c-text-soft,#8b95a5);margin-left:3px}
.aev-card-s{font-size:12px;color:var(--c-text-soft,#8b95a5);font-weight:600}
.aev-err{color:#c0392b;font-weight:800}
.aev-pending{display:flex;align-items:center;gap:8px;flex-wrap:wrap;background:#fbf1e0;border:1px solid #f0dcbb;
  color:#8a5320;border-radius:12px;padding:11px 14px;font-size:13px;font-weight:700;margin-bottom:12px}
.aev-flush{margin-left:auto;display:inline-flex;align-items:center;gap:5px;background:#1268d3;color:#fff;border:none;
  border-radius:9px;padding:8px 13px;font-size:12.5px;font-weight:800;cursor:pointer}
.aev-flush:disabled{opacity:.5}
.aev-msg{background:#eef7f0;border:1px solid #bfe3c9;color:#1f7a4d;border-radius:10px;padding:9px 13px;
  font-size:12.5px;font-weight:700;margin-bottom:12px}
.aev-tablewrap{overflow-x:auto;border:1px solid var(--c-border,#e3e8ef);border-radius:13px}
.aev-table{width:100%;border-collapse:collapse;font-size:12.5px;min-width:620px}
.aev-table th{background:#f4f7fb;color:#5a6b80;font-weight:800;text-align:left;padding:10px 12px;white-space:nowrap}
.aev-table td{padding:9px 12px;border-top:1px solid #eef2f7;color:var(--c-text,#33425a);white-space:nowrap}
.aev-empty{text-align:center;color:#8b95a5;padding:28px !important}
.aev-kind{font-weight:800;padding:2px 9px;border-radius:20px;font-size:11.5px}
.aev-kind.coffee{background:#f6ecdb;color:#8a5320}
.aev-kind.lollipop{background:#fdeef4;color:#c0396f}
.aev-st{font-weight:800;font-size:11.5px}
.aev-st.issued{color:#1f7a4d}
.aev-st.pending{color:#b06a1f}
.aev-st.used{color:#8b95a5}
.aev-phone{font-variant-numeric:tabular-nums;color:var(--c-text-soft,#5a6b80)}
      `}</style>
    </div>
  );
}
