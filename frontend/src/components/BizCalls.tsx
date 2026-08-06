import { useEffect, useState, useCallback } from "react";
import { Phone, PhoneIncoming, PhoneMissed, PhoneOutgoing, UserPlus, X } from "lucide-react";
import { useAuth } from "../auth";

const API = import.meta.env.VITE_API_BASE;

type CallItem = { phone: string; direction: string; at: string | null; duration_s: number; name: string | null };

function fmtPhone(p: string) {
  const d = (p || "").replace(/[^0-9]/g, "");
  if (d.length === 11) return `${d.slice(0, 3)}-${d.slice(3, 7)}-${d.slice(7)}`;
  if (d.length === 10) return `${d.slice(0, 3)}-${d.slice(3, 6)}-${d.slice(6)}`;
  return p;
}
function fmtDur(s: number) {
  if (!s) return "";
  const m = Math.floor(s / 60), ss = s % 60;
  return m ? `${m}분 ${ss}초` : `${ss}초`;
}
function fmtWhen(at: string | null) {
  if (!at) return "";
  return at.slice(2, 16).replace("-", ".").replace("-", ".").replace("T", " ");
}

// 미등록 번호를 고객으로 즉시 등록
export function QuickAddCustomer({ phone, onClose, onDone }: {
  phone: string; onClose: () => void; onDone?: () => void;
}) {
  const { token } = useAuth();
  const [name, setName] = useState("");
  const [memo, setMemo] = useState("");
  const [busy, setBusy] = useState(false);

  const save = async () => {
    if (!name.trim() || !API || !token) return;
    setBusy(true);
    try {
      const r = await fetch(`${API}/biz/customers/quick-add`, {
        method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ phone, name: name.trim(), memo: memo.trim() }),
      });
      if (!r.ok) { const d = await r.json().catch(() => ({})); alert(d?.detail?.message || d?.detail || "등록 실패"); setBusy(false); return; }
      onDone?.(); onClose();
    } catch { alert("일시적인 오류예요."); setBusy(false); }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" style={{ maxWidth: 380 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <span className="modal-title"><UserPlus size={16} /> 고객으로 등록</span>
          <button className="phone-banner-x" onClick={onClose} aria-label="닫기"><X size={16} /></button>
        </div>
        <p className="muted" style={{ fontSize: 13, margin: "4px 0 10px" }}>{fmtPhone(phone)} 번호를 내 사무소 고객으로 저장합니다.</p>
        <label className="modal-label">고객 이름</label>
        <input className="ai-input" value={name} autoFocus placeholder="예: 김OO"
          onChange={(e) => setName(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") save(); }} />
        <label className="modal-label" style={{ marginTop: 8 }}>메모 <span className="muted">(선택)</span></label>
        <input className="ai-input" value={memo} placeholder="예: 래미안 32평 매수 희망"
          onChange={(e) => setMemo(e.target.value)} />
        <button className="ai-send modal-cta" style={{ marginTop: 12, width: "100%" }} disabled={busy || !name.trim()} onClick={save}>
          {busy ? "저장 중…" : "고객 등록"}
        </button>
      </div>
    </div>
  );
}

const DIR: Record<string, { Icon: typeof Phone; label: string; color: string }> = {
  in: { Icon: PhoneIncoming, label: "수신", color: "#1f9d63" },
  out: { Icon: PhoneOutgoing, label: "발신", color: "#1268d3" },
  missed: { Icon: PhoneMissed, label: "부재중", color: "#d23b3b" },
};

// 통화 기록 — 수신/부재중·통화시간, 미등록 번호엔 '고객 등록' 버튼
export default function BizCalls() {
  const { token } = useAuth();
  const [items, setItems] = useState<CallItem[] | null>(null);
  const [addPhone, setAddPhone] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!token || !API) return;
    fetch(`${API}/biz/calls?limit=80`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json()).then((d) => setItems(d.items ?? [])).catch(() => setItems([]));
  }, [token]);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="biz-calls">
      <p className="muted" style={{ fontSize: 12.5, margin: "0 0 10px" }}>
        전화 고객알림을 켜두면, 고객 전화가 오갈 때마다 여기에 기록돼요. 미등록 번호는 바로 고객으로 등록할 수 있어요.
      </p>
      {items == null && <div className="muted" style={{ fontSize: 13 }}>불러오는 중…</div>}
      {items && items.length === 0 && (
        <div className="muted" style={{ fontSize: 13, padding: "20px 0", textAlign: "center" }}>
          아직 통화 기록이 없어요. 전화 고객알림을 켜면 쌓입니다.
        </div>
      )}
      {items && items.map((c, i) => {
        const d = DIR[c.direction] || DIR.in;
        return (
          <div key={i} className="bcl-row">
            <d.Icon size={16} style={{ color: d.color, flexShrink: 0 }} />
            <div className="bcl-main">
              <div className="bcl-top">
                <b>{c.name || fmtPhone(c.phone)}</b>
                {c.name && <span className="bcl-ph">{fmtPhone(c.phone)}</span>}
                {!c.name && <span className="bcl-new">미등록</span>}
              </div>
              <div className="bcl-sub">{d.label}{c.duration_s ? ` · ${fmtDur(c.duration_s)}` : ""} · {fmtWhen(c.at)}</div>
            </div>
            {!c.name && (
              <button className="bcl-add" onClick={() => setAddPhone(c.phone)}><UserPlus size={13} /> 등록</button>
            )}
          </div>
        );
      })}
      {addPhone && <QuickAddCustomer phone={addPhone} onClose={() => setAddPhone(null)} onDone={load} />}
    </div>
  );
}
