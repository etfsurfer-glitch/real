import { useCallback, useEffect, useState } from "react";
import { Sparkles, RefreshCw, Phone, Building2 } from "lucide-react";
import { useAuth } from "../auth";

const API = import.meta.env.VITE_API_BASE;

type Office = { realtor_id: string; name: string; status: string;
                read_at: string | null; responded_at: string | null };
type Req = {
  id: number; name: string; phone: string; region: string; asset: string; trade: string;
  area: string; budget: string; memo: string; ai_query: string; pick_mode: string;
  target_count: number; status: string; at: string; member_no: number | null; offices: Office[];
};

const ST = { sent: "전달됨", read: "읽음", responded: "연락함", declined: "보류" } as const;

/** 관리자 — 콕집요청 접수 현황. 손님 연락처가 보이므로 관리자만 들어온다. */
export default function AdminRequests() {
  const { token } = useAuth();
  const [items, setItems] = useState<Req[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState<number | null>(null);

  const load = useCallback(() => {
    if (!token) return;
    setLoading(true);
    fetch(`${API}/admin/requests?limit=200`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json()).then((d) => setItems(d.items || []))
      .catch(() => setItems([])).finally(() => setLoading(false));
  }, [token]);
  useEffect(() => { load(); }, [load]);

  const today = items.filter((r) => (r.at || "").slice(0, 10) === new Date().toISOString().slice(0, 10));
  const waiting = items.filter((r) => r.offices.every((o) => o.status === "sent"));

  return (
    <div className="areq">
      <div className="areq-head">
        <h2><Sparkles size={20} strokeWidth={2.3} /> 콕집요청</h2>
        <button className="areq-refresh" onClick={load} disabled={loading}>
          <RefreshCw size={14} strokeWidth={2.4} /> 새로고침
        </button>
      </div>
      <div className="areq-sum">
        전체 <b>{items.length}</b>건 · 오늘 <b>{today.length}</b>건 ·
        아직 아무도 안 읽은 요청 <b>{waiting.length}</b>건
      </div>

      {loading && items.length === 0 ? <div className="muted">불러오는 중…</div>
        : items.length === 0 ? <div className="muted">아직 접수된 요청이 없습니다.</div> : (
          <div className="areq-list">
            {items.map((r) => (
              <div key={r.id} className="areq-card">
                <div className="areq-top" onClick={() => setOpen(open === r.id ? null : r.id)}>
                  <div>
                    <div className="areq-title">
                      {r.region || "지역 미지정"} · {r.asset} {r.trade}
                      {r.area ? ` · ${r.area}` : ""}{r.budget ? ` · ${r.budget}` : ""}
                    </div>
                    <div className="areq-sub">
                      <span className="areq-name">{r.name || "이름 없음"}</span>
                      <a className="areq-phone" href={`tel:${r.phone}`}><Phone size={12} /> {r.phone}</a>
                      <span className="muted">{(r.at || "").slice(5, 16)}</span>
                      <span className="muted">
                        {r.pick_mode === "choose" ? "직접 선택" : "추천"} {r.target_count}곳
                      </span>
                    </div>
                  </div>
                  <div className="areq-badges">
                    {r.offices.map((o) => (
                      <span key={o.realtor_id} className={`areq-b areq-b-${o.status}`}>
                        {ST[o.status as keyof typeof ST] || o.status}
                      </span>
                    ))}
                  </div>
                </div>

                {open === r.id && (
                  <div className="areq-detail">
                    {r.memo && <div className="areq-memo"><b>요청 내용</b><br />{r.memo}</div>}
                    {r.ai_query && <div className="muted">AI 질문: {r.ai_query}</div>}
                    <div className="areq-offices">
                      {r.offices.map((o) => (
                        <div key={o.realtor_id} className="areq-office">
                          <Building2 size={14} />
                          <b>{o.name || o.realtor_id}</b>
                          <span className={`areq-b areq-b-${o.status}`}>
                            {ST[o.status as keyof typeof ST] || o.status}
                          </span>
                          <span className="muted">
                            {o.responded_at ? `연락 ${o.responded_at.slice(5, 16)}`
                              : o.read_at ? `읽음 ${o.read_at.slice(5, 16)}` : "미확인"}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
    </div>
  );
}
