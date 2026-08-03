import { useCallback, useEffect, useState } from "react";
import { Sparkles, RefreshCw, Phone, Building2, MessageSquare } from "lucide-react";
import { useAuth } from "../auth";

const API = import.meta.env.VITE_API_BASE;

type Phone = { phone: string; source: string };
type Office = { realtor_id: string; name: string; status: string;
                read_at: string | null; responded_at: string | null;
                is_member: boolean; channel: string;
                sms_phone: string | null; sms_at: string | null; sms_result: string | null;
                phones: Phone[] };
type OfferLs = { article_no: string; complex: string | null; area_m2: number | null;
                 price: string | null; rent: string | null; floor: string | null; trade: string };
type AOffer = { name: string; message: string; contact: string; listings: OfferLs[]; at: string };
type Req = {
  id: number; name: string; phone: string; region: string; asset: string; trade: string;
  area: string; budget: string; memo: string; ai_query: string; pick_mode: string;
  target_count: number; status: string; at: string; member_no: number | null; offices: Office[];
  offers: AOffer[]; escalated: number; last_escalated_at: string | null;
};
const PY_ = 3.305785;
const areaLb = (m2: number | null) => (m2 ? `${Math.round(m2 / PY_)}평(${Math.round(m2)}㎡)` : "");

const ST = { sent: "전달됨", read: "읽음", responded: "연락함", declined: "보류" } as const;

/** 관리자 — 콕집요청 접수 현황. 손님 연락처가 보이므로 관리자만 들어온다. */
export default function AdminRequests() {
  const { token } = useAuth();
  const [items, setItems] = useState<Req[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState<number | null>(null);
  const [pick, setPick] = useState<Record<string, string>>({});   // 사무소별 고른 번호
  const [sending, setSending] = useState("");
  const [msg, setMsg] = useState("");

  const load = useCallback(() => {
    if (!token) return;
    setLoading(true);
    fetch(`${API}/admin/requests?limit=200`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json()).then((d) => setItems(d.items || []))
      .catch(() => setItems([])).finally(() => setLoading(false));
  }, [token]);
  useEffect(() => { load(); }, [load]);

  /** 앱 미가입 사무소에 문자로 전달 — 관리자가 번호를 골라 보낸다. */
  const sendSms = async (reqId: number, o: Office) => {
    const key = `${reqId}:${o.realtor_id}`;
    const phone = pick[key] || o.phones[0]?.phone;
    if (!phone) { setMsg("보낼 번호가 없습니다."); return; }
    if (!confirm(`${o.name}\n${phone} 으로 손님 요청을 문자로 보낼까요?\n(손님 연락처가 함께 전송됩니다)`)) return;
    setSending(key); setMsg("");
    try {
      const r = await fetch(`${API}/admin/requests/${reqId}/sms`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ realtor_id: o.realtor_id, phone }),
      });
      const d = await r.json();
      setMsg(d.ok ? `${o.name} — 문자 발송 완료` : `발송 실패: ${d.detail || ""}`);
      load();
    } catch { setMsg("발송 실패"); } finally { setSending(""); }
  };

  /** 지금 3곳 더 보내기 — 무응답 요청을 관리자가 직접 넓힌다. */
  const escalate = async (id: number) => {
    if (!confirm("이 요청을 3곳에 더 보낼까요?\n(미가입 사무소에는 문자가 자동 발송됩니다)")) return;
    setSending(`esc${id}`); setMsg("");
    try {
      const r = await fetch(`${API}/admin/requests/${id}/escalate`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ count: 3 }),
      });
      const d = await r.json();
      setMsg(d.ok ? `${d.added}곳 추가 전달 (문자 ${d.sms}건) — ${(d.offices || []).join(", ")}`
                  : `추가 못 함: ${d.reason || ""}`);
      load();
    } catch { setMsg("추가 전달 실패"); } finally { setSending(""); }
  };

  const today = items.filter((r) => (r.at || "").slice(0, 10) === new Date().toISOString().slice(0, 10));
  const waiting = items.filter((r) => (r.offers || []).length === 0);

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
        제안 0건 <b>{waiting.length}</b>건
      </div>
      <div className="areq-hint">
        손님 연락처는 중개사무소에 전달되지 않습니다 — 조건만 갑니다.
        가입 사무소는 <b>앱 알림</b>, 미가입은 <b>문자 + 답장 링크</b>로 나갑니다.
        제안이 0건인 채 <b>30분</b>이 지나면 3곳씩 자동으로 더 보냅니다(최대 3회).
      </div>
      {msg && <div className="areq-msg">{msg}</div>}

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

                    <div className="areq-esc">
                      <span>
                        전달 {r.offices.length}곳 · 제안 <b>{(r.offers || []).length}건</b>
                        {r.escalated > 0 && ` · 자동확대 ${r.escalated}회`}
                        {r.last_escalated_at && ` (${r.last_escalated_at.slice(5, 16)})`}
                      </span>
                      <button disabled={sending === `esc${r.id}`} onClick={() => escalate(r.id)}>
                        {sending === `esc${r.id}` ? "보내는 중…" : "지금 3곳 더 보내기"}
                      </button>
                    </div>

                    {(r.offers || []).length > 0 && (
                      <div className="areq-offers">
                        <b>받은 제안</b>
                        {r.offers.map((o, i) => (
                          <div key={i} className="areq-offer">
                            <div className="areq-offer-h">
                              <b>{o.name}</b>
                              <span>{o.contact}</span>
                              <span className="muted">{(o.at || "").slice(5, 16)}</span>
                            </div>
                            {o.message && <div>{o.message}</div>}
                            {o.listings.length > 0 && (
                              <div className="muted">
                                매물 {o.listings.length}건 — {o.listings.slice(0, 3).map((x) =>
                                  `${x.complex || "?"} ${areaLb(x.area_m2)} ${x.price || x.rent || ""}`).join(" / ")}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                    <div className="areq-offices">
                      {r.offices.map((o) => {
                        const key = `${r.id}:${o.realtor_id}`;
                        return (
                          <div key={o.realtor_id} className="areq-office">
                            <div className="areq-office-h">
                              <Building2 size={14} />
                              <b>{o.name || o.realtor_id}</b>
                              <span className={`areq-b ${o.is_member ? "areq-b-responded" : "areq-b-sent"}`}>
                                {o.is_member ? "앱 가입 · 알림 전달됨" : "미가입"}
                              </span>
                              <span className={`areq-b areq-b-${o.status}`}>
                                {ST[o.status as keyof typeof ST] || o.status}
                              </span>
                              <span className="muted">
                                {o.responded_at ? `연락 ${o.responded_at.slice(5, 16)}`
                                  : o.read_at ? `읽음 ${o.read_at.slice(5, 16)}` : "미확인"}
                              </span>
                            </div>

                            {!o.is_member && (
                              <div className="areq-sms">
                                {o.sms_at && (
                                  <div className="areq-sms-done">
                                    <MessageSquare size={13} /> {o.sms_at.slice(5, 16)} · {o.sms_phone} · {o.sms_result}
                                  </div>
                                )}
                                {o.phones.length === 0 ? (
                                  <span className="muted">등록된 번호가 없어 문자를 보낼 수 없습니다.</span>
                                ) : (
                                  <>
                                    <select value={pick[key] ?? o.phones[0].phone}
                                      onChange={(e) => setPick((v) => ({ ...v, [key]: e.target.value }))}>
                                      {o.phones.map((p) => (
                                        <option key={p.phone} value={p.phone}>
                                          {p.phone} — {p.source}
                                        </option>
                                      ))}
                                    </select>
                                    <button disabled={sending === key}
                                      onClick={() => sendSms(r.id, o)}>
                                      {sending === key ? "보내는 중…" : o.sms_at ? "다시 보내기" : "문자 보내기"}
                                    </button>
                                  </>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
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
